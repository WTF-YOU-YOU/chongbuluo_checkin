# chongbuluo_checkin

用于 `https://www.chongbuluo.com/` 的自动登录与打卡签到脚本（Python + Playwright）。

## 1) 安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
```

## 2) 配置账号

复制配置模板：

```powershell
Copy-Item .env.example .env
```

然后编辑 `.env`：

- `CHONGBULUO_USERNAME`：你的用户名
- `CHONGBULUO_PASSWORD`：你的密码
- 如果页面结构变化，调整 `USERNAME_SELECTOR`、`PASSWORD_SELECTOR`、`SUBMIT_SELECTOR`、`CHECKIN_SELECTOR`

## 3) 运行签到

```powershell
python checkin.py
```

首次建议把 `.env` 中 `HEADLESS=false`，观察浏览器过程；确认可用后再改为 `true`。

## 4) Windows 定时任务（可选）

可在“任务计划程序”里每天定时执行（示例命令）：

```powershell
powershell.exe -ExecutionPolicy Bypass -Command "cd 'C:\Users\CRRC-ZTB\Desktop\chongbuluo_checkin'; .\.venv\Scripts\python.exe .\checkin.py"
```

## 注意

- 网站若开启图形验证码、人机验证或登录保护，自动化可能失败，需要手动处理。
- 请遵守网站服务条款和相关规则，合理控制请求频率。

## GitHub Actions 自动打卡

已内置工作流文件：`.github/workflows/checkin.yml:1`。

1. 将仓库推送到 GitHub。
2. 打开仓库 `Settings -> Secrets and variables -> Actions -> New repository secret`。
3. 至少配置以下 secrets：
   - `CHONGBULUO_USERNAME`
   - `CHONGBULUO_PASSWORD`
4. 建议同时配置（避免使用默认值时页面不匹配）：
   - `LOGIN_URL`
   - `CHECKIN_URL`
   - `USERNAME_SELECTOR`
   - `PASSWORD_SELECTOR`
   - `SUBMIT_SELECTOR`
   - `CHECKIN_SELECTOR`

工作流默认每天 UTC 00:05 执行（北京时间 08:05），也可在 Actions 页面手动触发 `workflow_dispatch`。
