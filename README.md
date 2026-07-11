# 📡 GV-Pulse: Google Voice Keep-Alive Bot

![Status](https://img.shields.io/badge/Status-Active-brightgreen)
![License](https://img.shields.io/badge/License-MIT-blue)
![Python](https://img.shields.io/badge/Python-3.13-blue)
![GitHub Actions](https://img.shields.io/badge/Automation-GitHub--Actions-blueviolet)

**GV-Pulse** is an automated utility that prevents Google Voice numbers from expiring due to inactivity. It uses Gmail SMTP to send a monthly text message via the official Google Voice SMS gateway, simulating active usage with zero maintenance.

---

## ✨ Features

- **Automated Pulse** — Sends a monthly SMS to keep your number active.
- **Multi-Number Support** — Maintain any number of GV numbers with a single workflow run via a comma-separated gateway list.
- **Retry Logic with Backoff** — Automatically retries transient SMTP failures (up to 5 attempts per gateway) with exponential backoff and jitter, so a bad network blip doesn't hammer Gmail's servers.
- **Shared SMTP Session** — Authenticates once per run and reuses the connection across all gateways instead of reconnecting for each number.
- **Repository Keep-Alive** — Commits to `keepalive.log` after every run so GitHub never disables the scheduled workflow due to inactivity.
- **Ultra-Lightweight** — No third-party dependencies; runs entirely on GitHub's free-tier runners.
- **Private & Secure** — All credentials live in GitHub Secrets.

---

## 🏗️ How It Works

1. The Python script authenticates with Gmail SMTP and sends an email to an address ending in `@txt.voice.google.com`. Google routes this as an outgoing SMS from your GV number.
2. After a successful send the workflow commits a timestamped entry to `keepalive.log` on the `logs` branch, preventing GitHub from auto-disabling the Action after 60 days of inactivity.
3. If `GV_GATEWAYS` contains multiple comma-separated addresses, every number is pulsed in the same run, reusing one authenticated SMTP session. Any number that fails is retried on its own with backoff.

---

## 🚀 Quick Start: Fork & Activate

### 1. Fork this Repository
Click **Fork** at the top-right of this page.

### 2. Enable GitHub Actions
GitHub disables Actions on forks by default.
- Go to the **Actions** tab in your fork.
- Click **"I understand my workflows, go ahead and enable them"**.

### 3. Add Your Secrets
`Settings > Secrets and variables > Actions > New repository secret`

| Secret Name     | Required | Description |
| :-------------- | :------- | :---------- |
| `GMAIL_USER`    | ✅ Yes   | Your full Gmail address |
| `GMAIL_PASSWORD`| ✅ Yes   | Your 16-character Gmail App Password |
| `GV_GATEWAYS`   | ✅ Yes   | One or more `<number>@txt.voice.google.com` addresses, comma-separated (e.g. `5551234567@txt.voice.google.com,5559876543@txt.voice.google.com`) |

### 4. Grant Write Permissions
- `Settings > Actions > General > Workflow permissions`
- Select **Read and write permissions** → **Save**.

### 5. Manual Test (Optional)
- **Actions** tab → **GV-Pulse Keep-Alive** → **Run workflow**.

---

## 🛠️ Prerequisites

### Gmail App Password
Standard passwords won't work. Generate a 16-character **App Password** in  
`Google Account > Security > 2-Step Verification > App passwords`.

### Finding Your SMS Gateway Address
Send any SMS *to* your GV number from another phone. Reply via Gmail and inspect the `To:` field — it will end in `@txt.voice.google.com`. That full address is your gateway.

---

## ⏰ Schedule

The workflow runs at **09:45 UTC on the 1st of every month** by default.  
To change the frequency, edit the `cron` value in `.github/workflows/main.yml`.

---

## 📝 Execution Logs

Timestamped run history is stored in [`keepalive.log`](../../tree/logs/keepalive.log) on the `logs` branch.

---

## 📜 Disclaimer

This project is for personal use only. Use it responsibly and in accordance with Google's Terms of Service.

## ⚖️ License

Distributed under the [MIT License](LICENSE).