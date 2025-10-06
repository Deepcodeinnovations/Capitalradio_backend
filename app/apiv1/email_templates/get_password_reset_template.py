def get_password_reset_template(verification_code, expiration_minutes=15, year=2025):
    """
    Returns an HTML template for password reset emails.
    
    Args:
        verification_code: The password reset verification code
        expiration_minutes: How long the code is valid (default: 15 minutes)
        year: Copyright year for the footer
        
    Returns:
        str: Formatted HTML template
    """
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Password Reset</title>
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                margin: 0;
                padding: 0;
                background-color: #f9f9f9;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
                background-color: #ffffff;
                border-radius: 8px;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
            }}
            .header {{
                text-align: center;
                padding: 20px 0;
                border-bottom: 1px solid #eee;
            }}
            .logo {{
                max-width: 150px;
                height: auto;
            }}
            .content {{
                padding: 30px 20px;
            }}
            h1 {{
                color: #1a3a6d;
                font-size: 24px;
                margin-top: 0;
                margin-bottom: 20px;
            }}
            p {{
                margin-bottom: 20px;
                font-size: 16px;
            }}
            .code {{
                background-color: #f5f7fa;
                font-family: monospace;
                padding: 15px;
                text-align: center;
                font-size: 28px;
                letter-spacing: 5px;
                margin: 25px 0;
                color: #1a3a6d;
                border-radius: 5px;
                border: 1px dashed #ccc;
            }}
            .note {{
                font-size: 14px;
                color: #666;
                font-style: italic;
            }}
            .footer {{
                text-align: center;
                padding-top: 20px;
                border-top: 1px solid #eee;
                font-size: 14px;
                color: #666;
            }}
            .button {{
                display: inline-block;
                background-color: #1a3a6d;
                color: white;
                text-decoration: none;
                padding: 12px 25px;
                border-radius: 4px;
                font-weight: bold;
                margin: 20px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <img src="https://boomry.com/logo.png" alt="Boomry Logo" class="logo">
            </div>
            <div class="content">
                <h1>Password Reset Code</h1>
                <p>Hello,</p>
                <p>We received a request to reset your password. Use the code below to complete the process:</p>
                
                <div class="code">{verification_code}</div>
                
                <p>If you didn't request a password reset, please ignore this email or contact our support team if you have concerns.</p>
                
                <p class="note">This code will expire in {expiration_minutes} minutes for security reasons.</p>
            </div>
            <div class="footer">
                <p>&copy; {year} Boomry. All rights reserved.</p>
                <p>Deepcode Innovations Ltd, Kampala, Uganda</p>
            </div>
        </div>
    </body>
    </html>
    """
