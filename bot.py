import os
import base64
from email.mime.text import MIMEText
import asyncio
import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

# লগিং সেটআপ
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

# আপনার টেলিগ্রাম বট টোকেন
TELEGRAM_TOKEN = "8685835907:AAGKip_Tifu0fK0u2zD_zi_rdk0nnYsTXgQ"

# জিমেইল এপিআই স্কোপ
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# ইউজারদের মেসেজ সাময়িকভাবে ধরে রাখার জন্য ডিকশনারি
user_drafts = {}

def get_gmail_service():
    creds = None
    token_path = 'token.json'
    # একদম সহজ এবং ফিক্সড ফাইলের নাম
    client_secret_file = 'credentials.json'

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
            
    return build('gmail', 'v1', credentials=creds)

def send_email(service, recipient, message_body):
    message = MIMEText(message_body)
    message['to'] = recipient
    message['subject'] = "WhatsApp Support 1138573745272888"
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    body = {'raw': raw}
    sent_message = service.users().messages().send(userId="me", body=body).execute()
    return sent_message['id']

def check_reply(service, recipient):
    query = f"from:{recipient}"
    results = service.users().messages().list(userId="me", q=query).execute()
    messages = results.get('messages', [])
    return len(messages) > 0

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "স্বাগতম! জিমেইল অটোমেশন সিস্টেমে। মেসেজ পাঠাতে নিচের ফরম্যাট ব্যবহার করুন:\n\n"
        "**Compose email +249113244447 আপনার মেসেজ এখানে লিখুন**"
    )

# ইউজার টেক্সট ইনপুট হ্যান্ডেল করার ফাংশন
async def handle_message_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text.startswith("Compose email"):
        try:
            parts = text.split(" ", 2)
            recipient_phone_or_id = parts[1] # যেমন: +249113244447
            message_body = parts[2]
            
            # রিকোয়ারমেন্ট অনুযায়ী ফিক্সড রিসিভার ও সেন্ডার
            recipient_email = "support@support.whatsapp.com"
            sender_email = "givuvuvuvjvivj636@gmail.com"
            subject_text = "WhatsApp Support 1138573745272888"
            
            user_drafts[update.effective_chat.id] = {
                "recipient_email": recipient_email,
                "display_target": recipient_phone_or_id,
                "message_body": message_body
            }

            # "মেসেজ সেন্ড করুন" বাটন তৈরি
            keyboard = [[InlineKeyboardButton("মেসেজ সেন্ড করুন", callback_data="send_mail_btn")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"📤 **ইমেইল বিবরণী:**\n\n"
                f"**From:** {sender_email}\n"
                f"**To:** {recipient_email}\n"
                f"**Subject:** {subject_text}\n"
                f"**Target:** {recipient_phone_or_id}\n"
                f"**Message:** {message_body}\n\n"
                f"নিচের বাটনে ক্লিক করে মেসেজটি সেন্ড করুন:",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        except Exception as e:
            await update.message.reply_text("সঠিক ফরম্যাটে লিখুন: Compose email +249113244447 আপনার_মেসেজ")
    else:
        await update.message.reply_text("অনুগ্রহ করে 'Compose email +249113244447 <message>' ফরম্যাটে মেসেজ লিখুন।")

# বাটন ক্লিক করার পর ইমেইল পাঠানো এবং ৩০-৩৫ সেকেন্ড টাইমার শো করার লজিক
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    chat_id = query.message.chat_id
    if chat_id not in user_drafts:
        await query.edit_message_text("সেশন শেষ হয়ে গেছে। দয়া করে আবার নতুন করে মেসেজ লিখুন।")
        return

    data = user_drafts[chat_id]
    recipient_email = data["recipient_email"]
    message_body = f"Target: {data['display_target']}\n\n{data['message_body']}"

    try:
        service = get_gmail_service()
        send_email(service, recipient_email, message_body)
    except Exception as e:
        await query.edit_message_text(f"ইমেইল পাঠাতে সমস্যা হয়েছে: {str(e)}")
        return

    status_msg = await query.edit_message_text(
        f"✉️ ইমেইল সফলভাবে পাঠানো হয়েছে!\n⏳ রিপ্লাইয়ের জন্য অপেক্ষা করা হচ্ছে... (35s)"
    )

    # ৩০ থেকে ৩৫ সেকেন্ডের লাইভ কাউন্টডাউন এবং রিপ্লাই চেক লুপ
    for remaining in range(35, 0, -1):
        await asyncio.sleep(1)
        
        reply_received = False
        try:
            reply_received = check_reply(service, recipient_email)
        except Exception:
            pass

        if reply_received:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_msg.message_id,
                text="✅ কমপ্লিট! রিপ্লাই মেসেজ পাওয়া গেছে।"
            )
            return
        else:
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_msg.message_id,
                    text=f"✉️ ইমেইল পাঠানো হয়েছে।\n⏳ রিপ্লাইয়ের জন্য অপেক্ষা করা হচ্ছে... ({remaining}s remaining)"
                )
            except Exception:
                pass

    # যদি নির্দিষ্ট সময়ে রিপ্লাই না আসে
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text="⏰ সময়সীমা শেষ। নির্ধারিত সময়ের মধ্যে কোনো রিপ্লাই আসেনি।"
        )
    except Exception:
        pass

def main():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_input))
    application.add_handler(CallbackQueryHandler(button_callback, pattern="send_mail_btn"))

    application.run_polling()

if __name__ == "__main__":
    main()