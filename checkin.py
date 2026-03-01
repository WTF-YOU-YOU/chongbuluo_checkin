from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path

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


def split_selector_candidates(selector_text: str) -> list[str]:
    candidates = [item.strip() for item in selector_text.split("||") if item.strip()]
    return candidates if candidates else [selector_text]


def parse_bool(value: str | None, default: bool = True) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def env_or_default(key: str, default: str) -> str:
    value = os.getenv(key)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


def load_config() -> Config:
    load_dotenv()

    username = os.getenv("CHONGBULUO_USERNAME", "").strip()
    password = os.getenv("CHONGBULUO_PASSWORD", "").strip()
    if not username or not password:
        raise ValueError("请先在 .env 中配置 CHONGBULUO_USERNAME 和 CHONGBULUO_PASSWORD")

    return Config(
        username=username,
        password=password,
        login_url=env_or_default(
            "LOGIN_URL",
            "https://www.chongbuluo.com/member.php?mod=logging&action=login",
        ),
        checkin_url=env_or_default("CHECKIN_URL", "https://www.chongbuluo.com"),
        username_selector=env_or_default("USERNAME_SELECTOR", "input[name='username']"),
        password_selector=env_or_default("PASSWORD_SELECTOR", "input[name='password']"),
        submit_selector=env_or_default(
            "SUBMIT_SELECTOR",
            "button[type='submit'], input[type='submit']",
        ),
        checkin_selector=env_or_default(
            "CHECKIN_SELECTOR",
            "a[href*='qiandao'], a[href*='sign'], button:has-text('签到'), a:has-text('签到')",
        ),
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


def save_debug_artifacts(page, tag: str) -> None:
    debug_dir = Path("debug")
    debug_dir.mkdir(parents=True, exist_ok=True)
    safe_tag = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in tag)
    screenshot_path = debug_dir / f"{safe_tag}.png"
    html_path = debug_dir / f"{safe_tag}.html"
    page.screenshot(path=str(screenshot_path), full_page=True)
    html_path.write_text(page.content(), encoding="utf-8")
    print(f"已保存调试文件: {screenshot_path} / {html_path}")


def fill_first_available(page, selector_candidates: list[str], value: str, timeout_ms: int = 45000) -> str:
    deadline = time.monotonic() + timeout_ms / 1000
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        for frame in page.frames:
            for selector in selector_candidates:
                try:
                    node = frame.locator(selector).first
                    if node.count() > 0:
                        node.fill(value, timeout=1500)
                        return selector
                except Exception as exc:
                    last_error = exc
                    continue
        page.wait_for_timeout(500)
    raise RuntimeError(f"未找到可填写输入框，候选选择器: {selector_candidates}") from last_error


def click_first_available(page, selector_candidates: list[str], timeout_ms: int = 30000) -> str:
    deadline = time.monotonic() + timeout_ms / 1000
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        for frame in page.frames:
            for selector in selector_candidates:
                try:
                    node = frame.locator(selector).first
                    if node.count() > 0:
                        node.click(timeout=1500)
                        return selector
                except Exception as exc:
                    last_error = exc
                    continue
        page.wait_for_timeout(500)
    raise RuntimeError(f"未找到可点击按钮，候选选择器: {selector_candidates}") from last_error


def login(page, cfg: Config) -> None:
    print(f"[1/3] 打开登录页: {cfg.login_url}")
    page.goto(cfg.login_url, wait_until="domcontentloaded", timeout=45000)

    username_candidates = split_selector_candidates(cfg.username_selector) + [
        "input[id^='username']",
        "#ls_username",
        "input[name='username']",
    ]
    password_candidates = split_selector_candidates(cfg.password_selector) + [
        "input[id^='password']",
        "#ls_password",
        "input[name='password']",
    ]
    submit_candidates = split_selector_candidates(cfg.submit_selector) + [
        "button:has-text('登录')",
        "input[value*='登录']",
        "button[type='submit']",
        "input[type='submit']",
    ]

    try:
        used_user_selector = fill_first_available(page, username_candidates, cfg.username)
        used_pass_selector = fill_first_available(page, password_candidates, cfg.password)
        used_submit_selector = click_first_available(page, submit_candidates)
        print(
            "登录选择器: "
            f"username={used_user_selector}, password={used_pass_selector}, submit={used_submit_selector}"
        )
    except Exception:
        print(f"当前页面标题: {page.title()}")
        print(f"当前页面URL: {page.url}")
        save_debug_artifacts(page, "login_failed")
        raise

    page.wait_for_load_state("networkidle", timeout=30000)


def checkin(page, cfg: Config) -> bool:
    print(f"[2/3] 打开签到页: {cfg.checkin_url}")
    page.goto(cfg.checkin_url, wait_until="domcontentloaded", timeout=45000)
    try_close_popups(page)

    button = page.locator(cfg.checkin_selector).first
    if button.count() == 0:
        save_debug_artifacts(page, "checkin_button_not_found")
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
