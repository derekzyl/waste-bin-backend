"""Telegram Bot service for sending alerts."""

from typing import Optional

import requests


class TelegramBot:
    """Telegram Bot API wrapper for sending security alerts."""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        """
        Initialize Telegram bot.

        Args:
            bot_token: Telegram bot token
            chat_id: Telegram chat ID
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = (
            f"https://api.telegram.org/bot{bot_token}" if bot_token else None
        )

    def send_image(self, image_path: str, caption: str) -> bool:
        """
        Send image to Telegram chat.

        Args:
            image_path: Path to image file
            caption: Image caption

        Returns:
            True if successful, False otherwise
        """
        if not self.bot_token or not self.chat_id:
            print("❌ Telegram bot not configured")
            return False

        try:
            url = f"{self.base_url}/sendPhoto"

            with open(image_path, "rb") as photo:
                files = {"photo": photo}
                data = {
                    "chat_id": self.chat_id,
                    "caption": caption,
                }

                response = requests.post(url, files=files, data=data, timeout=10)

                if response.status_code == 200:
                    print("✅ Telegram image sent successfully")
                    return True
                else:
                    print(
                        f"❌ Telegram API error: {response.status_code} - {response.text}"
                    )
                    return False

        except Exception as e:
            print(f"❌ Error sending Telegram image: {e}")
            return False

    def send_message(self, message: str) -> bool:
        """
        Send text message to Telegram chat.

        Args:
            message: Text message

        Returns:
            True if successful, False otherwise
        """
        if not self.bot_token or not self.chat_id:
            print("❌ Telegram bot not configured")
            return False

        try:
            url = f"{self.base_url}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
            }

            response = requests.post(url, data=data, timeout=10)

            if response.status_code == 200:
                print("✅ Telegram message sent successfully")
                return True
            else:
                print(
                    f"❌ Telegram API error: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            print(f"❌ Error sending Telegram message: {e}")
            return False

    def test_connection(self) -> bool:
        """
        Test Telegram bot connection.

        Returns:
            True if connection successful, False otherwise
        """
        if not self.bot_token:
            return False

        try:
            url = f"{self.base_url}/getMe"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                bot_info = response.json()
                print(
                    f"✅ Telegram bot connected: {bot_info.get('result', {}).get('username')}"
                )
                return True
            else:
                print(f"❌ Telegram bot connection failed: {response.status_code}")
                return False

        except Exception as e:
            print(f"❌ Error testing Telegram connection: {e}")
            return False
