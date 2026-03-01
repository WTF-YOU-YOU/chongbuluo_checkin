from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from dotenv import load_dotenv
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


@dataclass
class Config:
    username: str
    password: str
    login_url: str
    checkin_url: str
    username_selector: str
    password_selector: str
    submit_selector: str
    checkin_selector: str
    headless: bool


def parse_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_config() -> Config:
    load_dotenv()

    username = os.getenv("CHONGBULUO_USERNAME", "").strip()
    password = os.getenv("CHONGBULUO_PASSWORD", "").strip()
    if not username or not password:
        raise ValueError("请先在 .env 中配置 CHONGBULUO_USERNAME 和 CHONGBULUO_PASSWORD")

    return Config(
        username=username,
        password=password,
        login_url=os.getenv(
            "LOGIN_URL",
            "https://www.chongbuluo.com/member.php?mod=logging&action=login",
        ).strip(),
        checkin_url=os.getenv("CHECKIN_URL", "https://www.chongbuluo.com").strip(),
        username_selector=os.getenv("USERNAME_SELECTOR", "input[name='username']").strip(),
        password_selector=os.getenv("PASSWORD_SELECTOR", "input[name='password']").strip(),
        submit_selector=os.getenv(
            "SUBMIT_SELECTOR",
            "button[type='submit'], input[type='submit']",
        ).strip(),
        checkin_selector=os.getenv(
            "CHECKIN_SELECTOR",
            "a[href*='qiandao'], a[href*='sign'], button:has-text('签到'), a:has-text('签到')",
        ).strip(),
        headless=parse_bool(os.getenv("HEADLESS"), default=True),
    )


def try_close_popups(page) -> None:
    popup_selectors = [
        "button:has-text('关闭')",
        "button:has-text('我知道了')",
        "a:has-text('关闭')",
        ".close",
    ]
    for selector in popup_selectors:
        try:
            node = page.locator(selector).first
            if node.is_visible(timeout=500):
                node.click(timeout=1000)
        except Exception:
            continue


def login(page, cfg: Config) -> None:
    print(f"[1/3] 打开登录页: {cfg.login_url}")
    page.goto(cfg.login_url, wait_until="domcontentloaded", timeout=45000)

    page.fill(cfg.username_selector, cfg.username, timeout=15000)
    page.fill(cfg.password_selector, cfg.password, timeout=15000)
    page.locator(cfg.submit_selector).first.click(timeout=15000)
    page.wait_for_load_state("networkidle", timeout=30000)


def checkin(page, cfg: Config) -> bool:
    print(f"[2/3] 打开签到页: {cfg.checkin_url}")
    page.goto(cfg.checkin_url, wait_until="domcontentloaded", timeout=45000)
    try_close_popups(page)

    button = page.locator(cfg.checkin_selector).first
    if button.count() == 0:
        print("未找到签到按钮，请检查 CHECKIN_SELECTOR。")
        return False

    button.click(timeout=15000)
    page.wait_for_timeout(2000)

    content = page.content()
    success_keywords = ["签到成功", "已签到", "打卡成功", "已打卡", "恭喜"]
    if any(keyword in content for keyword in success_keywords):
        print("[3/3] 签到成功。")
        return True

    print("[3/3] 已点击签到按钮，但未检测到明确成功文案，请手动确认页面。")
    return True


def main() -> int:
    try:
        cfg = load_config()
    except Exception as exc:
        print(f"配置错误: {exc}")
        return 2

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=cfg.headless)
            context = browser.new_context()
            page = context.new_page()

            login(page, cfg)
            ok = checkin(page, cfg)

            context.close()
            browser.close()
            return 0 if ok else 1
    except PlaywrightTimeoutError as exc:
        print(f"页面超时: {exc}")
        return 3
    except Exception as exc:
        print(f"执行失败: {exc}")
        return 4


if __name__ == "__main__":
    sys.exit(main())
