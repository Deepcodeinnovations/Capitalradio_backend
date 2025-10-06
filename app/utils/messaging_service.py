import smtplib
import requests
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Optional, List, Union
import logging

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

class MessagingService:
    def __init__(self):
        # SMS Configuration from environment variables
        self.sms_config = {
            "username": os.getenv("SMS_USERNAME", ""),
            "password": os.getenv("SMS_PASSWORD", ""),
            "sender": os.getenv("SMS_SENDER", ""),
            "base_url": os.getenv("SMS_BASE_URL", "www.egosms.co/api/v1/plain/?")
        }
        
        # Email Configuration from environment variables
        self.email_config = {
            "host": os.getenv("EMAIL_HOST", ""),
            "port": int(os.getenv("EMAIL_PORT", "587")),
            "username": os.getenv("EMAIL_USERNAME", ""),
            "password": os.getenv("EMAIL_PASSWORD", ""),
            "encryption": os.getenv("EMAIL_ENCRYPTION", "ssl"),
            "from_email": os.getenv("EMAIL_FROM_ADDRESS", ""),
            "from_name": os.getenv("EMAIL_FROM_NAME", "Boomry")
        }

        # Validate configurations
        self._validate_config()

    def _validate_config(self):
        missing_sms = [k for k, v in self.sms_config.items() if not v]
        if missing_sms:
            logger.warning(f"Missing SMS configuration: {', '.join(missing_sms)}")
            
        missing_email = [k for k, v in self.email_config.items() 
                         if not v and k not in ["encryption", "from_name"]]
        if missing_email:
            logger.warning(f"Missing email configuration: {', '.join(missing_email)}")



    async def send_sms(self, phone_number: str, message: str) -> Dict:
        try:
            # Check if required configuration is available
            required_keys = ["username", "password", "sender", "base_url"]
            if any(not self.sms_config.get(key) for key in required_keys):
                return {
                    "status": "error",
                    "message": "SMS configuration is incomplete"
                }
                
            # Construct the URL for the API request
            url = f"https://{self.sms_config['base_url']}username={self.sms_config['username']}&password={self.sms_config['password']}&sender={self.sms_config['sender']}&to={phone_number}&message={message}"
            
            # Send the request
            response = requests.get(url)
            
            if response.status_code == 200:
                logger.info(f"SMS sent successfully to {phone_number}")
                return {
                    "status": "success",
                    "message": "SMS sent successfully"
                }
            else:
                logger.error(f"Failed to send SMS: {response.text}")
                return {
                    "status": "error",
                    "message": f"Failed to send SMS: {response.text}"
                }
                
        except Exception as e:
            logger.exception(f"Error sending SMS: {str(e)}")
            return {
                "status": "error",
                "message": f"Exception occurred: {str(e)}"
            }


    async def send_email( self, recipient_email: str,  subject: str,  html_content: str) -> Dict:
        try:
            print(self.email_config)
            # Check if required configuration is available
            required_keys = ["host", "port", "username", "password", "from_email"]
            if any(not self.email_config.get(key) for key in required_keys):
                return {
                    "status": "error",
                    "message": "Email configuration is incomplete"
                }

            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.email_config['from_name']} <{self.email_config['from_email']}>"
            msg['To'] = recipient_email
            
            # Add a plain text version derived from HTML
            import re
            text_version = re.sub('<.*?>', '', html_content)
            msg.attach(MIMEText(text_version, 'plain'))
                
            # Add HTML content
            msg.attach(MIMEText(html_content, 'html'))
            
            # Connect to SMTP server and send
            server = None
            try:
                if self.email_config['encryption'].lower() == 'ssl':
                    server = smtplib.SMTP_SSL(self.email_config['host'], self.email_config['port'])
                else:
                    server = smtplib.SMTP(self.email_config['host'], self.email_config['port'])
                    if self.email_config['encryption'].lower() == 'tls':
                        server.starttls()
                        
                server.login(self.email_config['username'], self.email_config['password'])
                server.sendmail(self.email_config['from_email'], recipient_email, msg.as_string())
                
                logger.info(f"Email sent successfully to {recipient_email}")
                return {
                    "status": "success",
                    "message": "Email sent successfully"
                }
            finally:
                if server:
                    server.quit()
            
        except Exception as e:
            logger.exception(f"Error sending email: {str(e)}")
            return {
                "status": "error",
                "message": f"Exception occurred: {str(e)}"
            }