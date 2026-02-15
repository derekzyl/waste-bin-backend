"""Telegram Bot service for sending alerts."""

from typing import Optional, Tuple

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
            image_path: Path to image file or URL
            caption: Image caption

        Returns:
            True if successful, False otherwise
        """
        if not self.bot_token or not self.chat_id:
            print("❌ Telegram bot not configured")
            return False

        try:
            url = f"{self.base_url}/sendPhoto"

            # Check if image_path is a URL (starts with http) or local file
            if image_path.startswith("http://") or image_path.startswith("https://"):
                # Send photo from URL
                data = {
                    "chat_id": self.chat_id,
                    "photo": image_path,
                    "caption": caption,
                }
                response = requests.post(url, data=data, timeout=10)
            else:
                # Send photo from local file
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
            elif response.status_code == 404:
                print(
                    "❌ Telegram 404: Bot not found. Check bot token and chat_id."
                )
                return False
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
            elif response.status_code == 404:
                print(
                    "❌ Telegram 404: Bot not found. Check bot token (from @BotFather) and chat_id (send /start to bot, then get from getUpdates)."
                )
                return False
            else:
                print(
                    f"❌ Telegram API error: {response.status_code} - {response.text}"
                )
                return False

        except Exception as e:
            print(f"❌ Error sending Telegram message: {e}")
            return False

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test Telegram bot connection.

        Returns:
            (True, "") if OK, (False, "error message") otherwise
        """
        if not self.bot_token:
            return False, "Bot token not set"

        try:
            url = f"{self.base_url}/getMe"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                bot_info = response.json()
                print(
                    f"✅ Telegram bot connected: {bot_info.get('result', {}).get('username')}"
                )
                return True, ""
            elif response.status_code == 404:
                msg = "Invalid bot token. Get a new token from @BotFather and update Telegram config."
                print(f"❌ Telegram 404: {msg}")
                return False, msg
            else:
                msg = f"Telegram API returned {response.status_code}"
                print(f"❌ Telegram bot connection failed: {msg}")
                return False, msg

        except Exception as e:
            msg = str(e)
            print(f"❌ Error testing Telegram connection: {e}")
            return False, msg


# ============================================================================
# Standalone Helper Functions
# ============================================================================


def send_image_to_telegram(
    bot_token: str,
    chat_id: str,
    image_path: str,
    caption: str
) -> bool:
    """
    Send image to Telegram chat (standalone function).

    Args:
        bot_token: Telegram bot token
        chat_id: Telegram chat ID
        image_path: Path to image file or URL
        caption: Image caption

    Returns:
        True if successful, False otherwise
    """
    bot = TelegramBot(bot_token, chat_id)
    return bot.send_image(image_path, caption)


def send_message_to_telegram(
    bot_token: str,
    chat_id: str,
    message: str
) -> bool:
    """
    Send message to Telegram chat (standalone function).

    Args:
        bot_token: Telegram bot token
        chat_id: Telegram chat ID
        message: Text message

    Returns:
        True if successful, False otherwise
    """
    bot = TelegramBot(bot_token, chat_id)
    return bot.send_message(message)
