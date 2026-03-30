import aiosmtplib
from email.mime.text import MIMEText
from fastapi import HTTPException
from app.core.config import get_settings

settings = get_settings()

async def send_email(to: str, subject: str, body: str):
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to
    
    try:
        server = aiosmtplib.SMTP(
            hostname=settings.SMTP_SERVER,
            port=settings.SMTP_PORT,
            use_tls=False,
        )

        await server.connect()
        
        if server.use_tls:
            await server.starttls()
            
        await server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        await server.send_message(msg)
        await server.quit()

        return True

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email sending failed: {str(e)}")