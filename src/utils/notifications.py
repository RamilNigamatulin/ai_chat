import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()


class NotificationManager:
    """
    Менеджер уведомлений о низком балансе.
    Поддерживает отправку через Email и Telegram.
    """

    def __init__(self):
        self.method = os.getenv("NOTIFICATION_METHOD", "none").lower()
        self.threshold = float(os.getenv("LOW_BALANCE_THRESHOLD", "5.0"))

        # Настройки Email
        self.smtp_server = os.getenv("SMTP_SERVER")
        self.smtp_port = int(os.getenv("SMTP_PORT", 587))
        self.smtp_email = os.getenv("SMTP_EMAIL")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.admin_email = os.getenv("ADMIN_EMAIL")

        # Настройки Telegram
        self.tg_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.tg_chat_id = os.getenv("TELEGRAM_CHAT_ID")

    def send_email(self, subject: str, body: str):
        """Отправка уведомления через Email"""
        try:
            msg = MIMEMultipart()
            msg["From"] = self.smtp_email
            msg["To"] = self.admin_email
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_email, self.smtp_password)
                server.send_message(msg)
            print("✅ Email уведомление отправлено")
        except Exception as e:
            print(f"❌ Ошибка отправки Email: {e}")

    def send_telegram(self, message: str):
        """Отправка уведомления через Telegram"""
        try:
            import telebot

            bot = telebot.TeleBot(self.tg_token)
            bot.send_message(self.tg_chat_id, message)
            print("✅ Telegram уведомление отправлено")
        except Exception as e:
            print(f"❌ Ошибка отправки Telegram: {e}")

    def notify_low_balance(self, current_balance: float):
        """
        Проверяет баланс и отправляет уведомление, если он ниже порога.
        """
        if self.method == "none":
            return

        if current_balance <= self.threshold:
            subject = "⚠️ Внимание: Низкий баланс на OpenRouter!"
            body = f"Баланс вашего аккаунта OpenRouter упал до ${current_balance:.2f}.\nПорог предупреждения: ${self.threshold:.2f}.\nПожалуйста, пополните счет, чтобы избежать остановки работы приложения."

            if self.method in ["email", "both"]:
                self.send_email(subject, body)

            if self.method in ["telegram", "both"]:
                self.send_telegram(body)
