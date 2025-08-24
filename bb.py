import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request, redirect, session
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from web3 import Web3
import time
import os


# --- CONFIG ---
BOT_TOKEN = "7321121913:AAGQ60lqsi05KB4NXlnVxpAAnAE5mXFQxg8"
TG_CHANNEL_USERNAME = "studyverseclass10"  # Without @ symbol
TG_CHANNEL_ID = "@studyverseclass10"  # With @ for display
YT_CHANNEL_1 = "UC_x5XG1OV2P6uZZ5FSM9Ttw"  # Google Developer
YT_CHANNEL_2 = "UCq-Fj5jknLsUf-MWSy4_brA"  # YouTube India

# Use environment variable for base URL, fallback to localhost for development
BASE_URL = os.environ.get('BASE_URL', 'https://botcry.onrender.com')
# Alternative: Render provides RENDER_EXTERNAL_URL automatically
# BASE_URL = os.environ.get('RENDER_EXTERNAL_URL', 'http://localhost:5000')

SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]

# Web3 config - use environment variables for security
RPC_URL = "https://bsc-dataseed.binance.org/"
PRIVATE_KEY = os.environ.get('PRIVATE_KEY', 'YOUR_PRIVATE_KEY')
SENDER_ADDRESS = os.environ.get('SENDER_ADDRESS', '0xYourFundingWallet')
REWARD_AMOUNT = 0.0005

w3 = Web3(Web3.HTTPProvider(RPC_URL))

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your_random_secret_key_here')

# --- In-memory state ---
user_state = {}  # {tg_id: {"step": int, "wallet": str, "yt_verified": []}}


# --- Helper functions ---
def check_tg_membership(user_id):
    """Check if user is member of Telegram channel"""
    try:
        member = bot.get_chat_member(TG_CHANNEL_ID, user_id)
        return member.status in ['member', 'administrator', 'creator']
    except Exception as e:
        print(f"Error checking membership: {e}")
        return False


# --- Telegram handlers ---
@bot.message_handler(commands=["start"])
def start(msg):
    tg_id = msg.chat.id
    user_state[tg_id] = {"step": 1, "yt_verified": []}
    
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton("📱 Join Telegram Channel", url=f"https://t.me/{TG_CHANNEL_USERNAME}"),
        InlineKeyboardButton("✅ Verify Telegram Membership", callback_data="verify_tg")
    )
    
    bot.send_message(
        tg_id,
        f"🎯 Welcome to the Reward Bot!\n\n"
        f"📋 **Steps to earn rewards:**\n"
        f"1️⃣ Join our Telegram channel\n"
        f"2️⃣ Subscribe to YouTube channels\n" 
        f"3️⃣ Get crypto rewards!\n\n"
        f"**Step 1: Join Telegram Channel**\n"
        f"👆 Click 'Join Telegram Channel' first, then verify!",
        reply_markup=markup,
        parse_mode='Markdown'
    )


@bot.callback_query_handler(func=lambda call: call.data == "verify_tg")
def verify_tg_membership(call):
    tg_id = call.message.chat.id
    state = user_state.get(tg_id)
    
    if not state:
        bot.answer_callback_query(call.id, "Please start with /start")
        return
    
    if check_tg_membership(tg_id):
        state["step"] = 2
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("🔗 Subscribe to Google Developers", 
                               url=f"https://www.youtube.com/channel/{YT_CHANNEL_1}?sub_confirmation=1"),
            InlineKeyboardButton("🔗 Subscribe to YouTube India", 
                               url=f"https://www.youtube.com/channel/{YT_CHANNEL_2}?sub_confirmation=1"),
            InlineKeyboardButton("✅ Verify YouTube Subscriptions", callback_data="start_yt_verify")
        )
        
        bot.edit_message_text(
            f"✅ **Telegram membership verified!**\n\n"
            f"**Step 2: Subscribe to YouTube Channels**\n\n"
            f"📺 Click the links above to subscribe to both channels.\n"
            f"⚠️ Make sure to subscribe to BOTH channels!\n\n"
            f"👆 Then click 'Verify YouTube Subscriptions'",
            chat_id=tg_id,
            message_id=call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown'
        )
        bot.answer_callback_query(call.id, "✅ Telegram verified!")
    else:
        bot.answer_callback_query(call.id, "❌ Please join the channel first!", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data == "start_yt_verify")
def start_yt_verification(call):
    tg_id = call.message.chat.id
    state = user_state.get(tg_id)
    
    if not state or state.get("step") != 2:
        bot.answer_callback_query(call.id, "Please complete previous steps first!")
        return
    
    # Start with first YouTube channel verification
    auth_url = f"{BASE_URL}/login?user_id={tg_id}&channel=1"
    
    bot.edit_message_text(
        f"**Step 2: YouTube Verification**\n\n"
        f"🔍 **Verifying Channel 1/2: Google Developers**\n\n"
        f"🔗 **Click this link to verify your subscription:**\n"
        f"`{auth_url}`\n\n"
        f"🔒 This will open Google OAuth - grant permissions to verify your subscription.\n"
        f"📱 After clicking, return to Telegram to continue.",
        chat_id=tg_id,
        message_id=call.message.message_id,
        parse_mode='Markdown'
    )
    bot.answer_callback_query(call.id, "Starting YouTube verification...")


# --- Flask OAuth flow ---
@app.route("/login")
def login():
    user_id = int(request.args.get("user_id"))
    channel = int(request.args.get("channel", 1))
    session["user_id"] = user_id
    session["channel"] = channel
    
    flow = Flow.from_client_secrets_file(
        "cc.json",  # Make sure this file exists
        scopes=SCOPES,
        redirect_uri=f"{BASE_URL}/callback"
    )
    auth_url, _ = flow.authorization_url(prompt="consent")
    return redirect(auth_url)


@app.route("/callback")
def callback():
    try:
        flow = Flow.from_client_secrets_file(
            "cc.json",
            scopes=SCOPES,
            redirect_uri=f"{BASE_URL}/callback"
        )
        flow.fetch_token(authorization_response=request.url)
        creds = flow.credentials
        
        user_id = session["user_id"]
        channel = session["channel"]
        youtube = build("youtube", "v3", credentials=creds)
        
        # Select channel to verify
        channel_id = YT_CHANNEL_1 if channel == 1 else YT_CHANNEL_2
        channel_name = "Google Developers" if channel == 1 else "YouTube India"
        
        # Check subscription
        res = youtube.subscriptions().list(
            part="snippet",
            mine=True,
            forChannelId=channel_id
        ).execute()
        
        is_subscribed = len(res.get("items", [])) > 0
        state = user_state.get(user_id, {})
        
        if is_subscribed:
            # Add to verified list
            if channel not in state.get("yt_verified", []):
                state.setdefault("yt_verified", []).append(channel)
            
            if len(state["yt_verified"]) == 1:
                # First channel verified, verify second
                auth_url = f"{BASE_URL}/login?user_id={user_id}&channel=2"
                
                bot.send_message(
                    user_id,
                    f"✅ **{channel_name} subscription verified!**\n\n"
                    f"🔍 **Now verifying Channel 2/2: YouTube India**\n\n"
                    f"🔗 **Click this link to verify your second subscription:**\n"
                    f"`{auth_url}`\n\n"
                    f"📱 After clicking, return to Telegram to continue.",
                    parse_mode='Markdown'
                )
            elif len(state["yt_verified"]) >= 2:
                # Both channels verified
                state["step"] = 3
                bot.send_message(
                    user_id,
                    f"🎉 **All verifications complete!**\n\n"
                    f"✅ Telegram channel: Joined\n"
                    f"✅ YouTube channel 1: Subscribed\n"
                    f"✅ YouTube channel 2: Subscribed\n\n"
                    f"**Step 3: Get Your Reward**\n"
                    f"💰 Send your BSC wallet address to receive {REWARD_AMOUNT} BNB!",
                    parse_mode='Markdown'
                )
        else:
            bot.send_message(
                user_id,
                f"❌ **Subscription not found!**\n\n"
                f"Please make sure you:\n"
                f"1. Subscribed to {channel_name}\n"
                f"2. Used the same Google account\n\n"
                f"Try subscribing again and verify.",
                parse_mode='Markdown'
            )
        
        return "<h2>✅ Verification Complete!</h2><p>You can close this window and return to Telegram.</p>"
        
    except Exception as e:
        user_id = session.get("user_id")
        if user_id:
            bot.send_message(user_id, f"⚠️ Verification error: {str(e)}")
        return f"<h2>❌ Error</h2><p>{str(e)}</p><p>Please try again.</p>"


# --- Wallet collection & payment ---
@bot.message_handler(func=lambda msg: True)
def collect_wallet(msg):
    tg_id = msg.chat.id
    state = user_state.get(tg_id)
    
    if not state or state.get("step") != 3:
        return
    
    wallet = msg.text.strip()
    
    if not w3.is_address(wallet):
        bot.send_message(
            tg_id, 
            "⚠️ **Invalid wallet address!**\n\n"
            "Please send a valid BSC wallet address (starts with 0x)",
            parse_mode='Markdown'
        )
        return
    
    try:
        # Send payment
        bot.send_message(tg_id, "⏳ Processing payment...")
        tx_hash = send_payment(wallet, REWARD_AMOUNT)
        
        state["step"] = 4
        state["wallet"] = wallet
        
        bot.send_message(
            tg_id,
            f"🎉 **Payment Sent Successfully!**\n\n"
            f"💰 Amount: {REWARD_AMOUNT} BNB\n"
            f"💳 Wallet: `{wallet}`\n"
            f"🔗 Transaction: `{tx_hash}`\n\n"
            f"🔍 Check BSCScan: https://bscscan.com/tx/{tx_hash}\n\n"
            f"✅ Thank you for participating!",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        bot.send_message(
            tg_id,
            f"⚠️ **Payment Failed!**\n\n"
            f"Error: {str(e)}\n\n"
            f"Please contact support if this continues.",
            parse_mode='Markdown'
        )


# --- Payment function ---
def send_payment(receiver, amount):
    """Send BNB payment to receiver wallet"""
    receiver = w3.to_checksum_address(receiver)
    nonce = w3.eth.get_transaction_count(SENDER_ADDRESS)
    
    # Get current gas price
    gas_price = w3.eth.gas_price
    
    txn = {
        "to": receiver,
        "value": w3.to_wei(amount, "ether"),
        "gas": 21000,
        "gasPrice": gas_price,
        "nonce": nonce,
    }
    
    signed = w3.eth.account.sign_transaction(txn, PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    return w3.to_hex(tx_hash)


# --- Error handlers ---
@bot.message_handler(commands=["help"])
def help_command(msg):
    bot.send_message(
        msg.chat.id,
        "🤖 **Reward Bot Help**\n\n"
        "**Commands:**\n"
        "/start - Start the reward process\n"
        "/help - Show this help\n"
        "/status - Check your progress\n\n"
        "**Process:**\n"
        "1️⃣ Join Telegram channel\n"
        "2️⃣ Subscribe to YouTube channels\n"
        "3️⃣ Send wallet address for reward",
        parse_mode='Markdown'
    )


@bot.message_handler(commands=["status"])
def status_command(msg):
    tg_id = msg.chat.id
    state = user_state.get(tg_id, {})
    step = state.get("step", 0)
    
    status_text = "📊 **Your Progress:**\n\n"
    
    if step >= 1:
        status_text += "✅ Bot started\n"
    if step >= 2:
        status_text += "✅ Telegram channel joined\n"
    if len(state.get("yt_verified", [])) >= 1:
        status_text += "✅ First YouTube channel verified\n"
    if len(state.get("yt_verified", [])) >= 2:
        status_text += "✅ Second YouTube channel verified\n"
    if step >= 4:
        status_text += "✅ Reward sent\n"
    
    if step == 0:
        status_text += "❌ Not started - use /start"
    elif step < 4:
        status_text += f"\n🔄 Current step: {step}/3"
    
    bot.send_message(tg_id, status_text, parse_mode='Markdown')


# --- Health check endpoint ---
@app.route("/")
def health_check():
    return "<h2>🤖 Bot is running!</h2><p>All systems operational.</p>"


# --- Run both Flask and Bot ---
if __name__ == "__main__":
    from threading import Thread

    def run_flask():
        port = int(os.environ.get("PORT", 8080))
        app.run(host="0.0.0.0", port=port)

    # Check if credentials file exists
    if not os.path.exists('cc.json'):
        print("⚠️  Warning: cc.json not found. Please add your Google OAuth credentials.")
    
    print(f"🌐 Base URL: {BASE_URL}")
    print("🚀 Starting Flask server...")
    Thread(target=run_flask, daemon=True).start()
    
    print("🤖 Starting Telegram bot...")
    print(f"📱 Telegram Channel: {TG_CHANNEL_ID}")
    print(f"📺 YouTube Channels: {YT_CHANNEL_1}, {YT_CHANNEL_2}")
    
    bot.polling(none_stop=True)

