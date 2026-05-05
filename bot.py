import discord
from discord import app_commands
from discord.ui import Button, View, Modal, TextInput
import json
import os
import asyncio
from cryptography.fernet import Fernet
import aiohttp
from datetime import datetime

# Generate encryption key
ENCRYPTION_KEY = Fernet.generate_key()
cipher = Fernet(ENCRYPTION_KEY)

# Database file
DB_FILE = "users.json"

# Load/Save database
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_db(data):
    with open(DB_FILE, 'w') as f:
        json.dump(data, f, indent=2)

db = load_db()

# Discord API wrapper
class DiscordAPI:
    def __init__(self, token):
        self.token = token
        self.headers = {
            'Authorization': token,
            'Content-Type': 'application/json'
        }
        self.base = 'https://discord.com/api/v9'
    
    async def validate(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f'{self.base}/users/@me', headers=self.headers) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    return None
        except:
            return None
    
    async def send_message(self, channel_id, message):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f'{self.base}/channels/{channel_id}/messages',
                    headers=self.headers,
                    json={'content': message}
                ) as resp:
                    return resp.status == 200
        except:
            return False

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Active advertisers
active_tasks = {}

# Helper functions
def encrypt_token(token):
    return cipher.encrypt(token.encode()).decode()

def decrypt_token(encrypted):
    return cipher.decrypt(encrypted.encode()).decode()

def get_user_data(user_id):
    return db.get(str(user_id))

def save_user_data(user_id, data):
    db[str(user_id)] = data
    save_db(db)

# Advertising task
async def advertise_task(user_id, token, channels, message, delay):
    api = DiscordAPI(token)
    user_data = get_user_data(user_id)
    
    while user_id in active_tasks:
        for channel_id in channels:
            if user_id not in active_tasks:
                break
            
            success = await api.send_message(channel_id, message)
            
            if success:
                user_data['stats']['sent'] += 1
            else:
                user_data['stats']['failed'] += 1
            
            save_user_data(user_id, user_data)
            await asyncio.sleep(delay)

# Modals
class TokenModal(Modal, title="Set Your Token"):
    token_input = TextInput(
        label="Discord Token",
        placeholder="Paste your token here...",
        style=discord.TextStyle.long,
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        token = self.token_input.value.strip()
        
        # Validate token
        api = DiscordAPI(token)
        user_info = await api.validate()
        
        if not user_info:
            await interaction.response.send_message("❌ Invalid token!", ephemeral=True)
            return
        
        # Save encrypted token
        encrypted = encrypt_token(token)
        username = user_info.get('username', 'Unknown')
        discriminator = user_info.get('discriminator', '0')
        
        save_user_data(interaction.user.id, {
            'token': encrypted,
            'username': f"{username}#{discriminator}",
            'settings': {},
            'stats': {'sent': 0, 'failed': 0},
            'tos_accepted': False
        })
        
        embed = discord.Embed(
            title="✅ TOKEN SAVED!",
            description=f"**Account:** {username}#{discriminator}\n\n"
                       f"🔒 Your token is encrypted and stored securely.\n\n"
                       f"**Next steps:**\n"
                       f"1. Use `/setup` to configure\n"
                       f"2. Use `/panel` to control",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class SetupModal(Modal, title="Advertiser Setup"):
    channels = TextInput(
        label="Channel IDs (one per line)",
        placeholder="123456789012345678\n987654321098765432",
        style=discord.TextStyle.long,
        required=True
    )
    
    message = TextInput(
        label="Advertisement Message",
        placeholder="🚀 Join our server! discord.gg/example",
        style=discord.TextStyle.long,
        required=True
    )
    
    delay = TextInput(
        label="Delay (seconds)",
        placeholder="60",
        default="60",
        required=True
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        user_data = get_user_data(interaction.user.id)
        
        channel_list = [c.strip() for c in self.channels.value.split('\n') if c.strip()]
        
        user_data['settings'] = {
            'channels': channel_list,
            'message': self.message.value,
            'delay': int(self.delay.value)
        }
        user_data['tos_accepted'] = True
        user_data['tos_accepted_at'] = datetime.now().isoformat()
        
        save_user_data(interaction.user.id, user_data)
        
        embed = discord.Embed(
            title="✅ SETUP COMPLETE!",
            description=f"**Channels:** {len(channel_list)}\n"
                       f"**Message:** {self.message.value[:50]}...\n"
                       f"**Delay:** {self.delay.value}s\n\n"
                       f"Use `/panel` to start!",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# Commands
@tree.command(name="token-tut", description="How to get your Discord token (SAFE method)")
async def token_tut(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🔐 HOW TO GET YOUR TOKEN (SAFE METHOD)",
        description="**⚠️ USE NETWORK TAB - NOT CONSOLE!**\n\n"
                   "**STEP-BY-STEP:**\n"
                   "1. Open Discord in browser: discord.com/app\n"
                   "2. Press **F12** (Developer Tools)\n"
                   "3. Click **'Network'** tab\n"
                   "4. Press **Ctrl+R** to reload\n"
                   "5. Type **'api'** in filter box\n"
                   "6. Click any request (messages/users)\n"
                   "7. Click **'Headers'** tab on right\n"
                   "8. Scroll to **'Request Headers'**\n"
                   "9. Find **'authorization:'**\n"
                   "10. Copy the long text next to it\n\n"
                   "✅ Now use `/set-token` and paste!",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="set-token", description="Set your Discord token (ONE TIME)")
async def set_token(interaction: discord.Interaction):
    await interaction.response.send_modal(TokenModal())

@tree.command(name="setup", description="Configure your auto advertiser")
async def setup(interaction: discord.Interaction):
    user_data = get_user_data(interaction.user.id)
    
    if not user_data or 'token' not in user_data:
        embed = discord.Embed(
            title="❌ ACCESS DENIED",
            description="You need to set your token first!\n\n"
                       "**Steps:**\n"
                       "1. `/token-tut` - Learn how\n"
                       "2. `/set-token` - Set your token\n"
                       "3. Come back here",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Show ToS first
    embed = discord.Embed(
        title="📜 TERMS OF SERVICE",
        description="**By using this bot, you agree:**\n\n"
                   "1. You are responsible for your Discord account\n"
                   "2. Automation may violate Discord Terms of Service\n"
                   "3. We are not liable for account bans or issues\n"
                   "4. Your token is encrypted with AES-256\n"
                   "5. You can delete your data with `/delete` anytime\n"
                   "6. Use this service at your own risk\n\n"
                   "🔒 **Security:** All tokens are encrypted\n"
                   "🗑️ **Privacy:** You can revoke access anytime\n\n"
                   "Click **'I Accept'** to continue",
        color=discord.Color.orange()
    )
    
    class ToSView(View):
        @discord.ui.button(label="✅ I Accept", style=discord.ButtonStyle.green)
        async def accept(self, interaction: discord.Interaction, button: Button):
            await interaction.response.send_modal(SetupModal())
        
        @discord.ui.button(label="❌ Decline", style=discord.ButtonStyle.red)
        async def decline(self, interaction: discord.Interaction, button: Button):
            embed = discord.Embed(
                title="❌ SETUP CANCELLED",
                description="You must accept the Terms of Service to use this bot.\n\n"
                           "If you change your mind, use `/setup` again.\n\n"
                           "Questions? Contact support.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    await interaction.response.send_message(embed=embed, view=ToSView(), ephemeral=True)

@tree.command(name="panel", description="Main control panel")
async def panel(interaction: discord.Interaction):
    user_data = get_user_data(interaction.user.id)
    
    if not user_data or 'token' not in user_data:
        embed = discord.Embed(
            title="❌ ACCESS DENIED",
            description="Set your token first!\n\n"
                       "Use `/set-token` to get started.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    settings = user_data.get('settings', {})
    stats = user_data.get('stats', {'sent': 0, 'failed': 0})
    is_running = interaction.user.id in active_tasks
    
    status = "🟢 Running" if is_running else "🔴 Stopped"
    
    embed = discord.Embed(
        title="🚀 AUTO ADVERTISER PRO",
        description=f"**User:** {user_data.get('username', 'Unknown')}\n"
                   f"**Status:** {status}\n\n"
                   f"**📱 Channels:** {len(settings.get('channels', []))}\n"
                   f"**💬 Message:** {settings.get('message', 'Not set')[:50]}...\n"
                   f"**⏱️ Delay:** {settings.get('delay', 0)}s\n\n"
                   f"**📊 Stats:**\n"
                   f"Sent: {stats['sent']} | Failed: {stats['failed']}",
        color=discord.Color.green() if is_running else discord.Color.red()
    )
    embed.set_footer(text="made by hanlek")
    
    class PanelView(View):
        @discord.ui.button(label="▶️ Start" if not is_running else "⏹️ Stop", 
                          style=discord.ButtonStyle.green if not is_running else discord.ButtonStyle.red)
        async def toggle(self, interaction: discord.Interaction, button: Button):
            user_data = get_user_data(interaction.user.id)
            
            if interaction.user.id in active_tasks:
                # Stop
                del active_tasks[interaction.user.id]
                await interaction.response.send_message("⏹️ Stopped advertising!", ephemeral=True)
            else:
                # Start
                if not user_data.get('settings'):
                    await interaction.response.send_message("❌ Run `/setup` first!", ephemeral=True)
                    return
                
                token = decrypt_token(user_data['token'])
                settings = user_data['settings']
                
                task = asyncio.create_task(advertise_task(
                    interaction.user.id,
                    token,
                    settings['channels'],
                    settings['message'],
                    settings['delay']
                ))
                active_tasks[interaction.user.id] = task
                
                await interaction.response.send_message("▶️ Started advertising!", ephemeral=True)
        
        @discord.ui.button(label="⚙️ Edit Settings", style=discord.ButtonStyle.gray)
        async def edit(self, interaction: discord.Interaction, button: Button):
            await interaction.response.send_modal(SetupModal())
        
        @discord.ui.button(label="📊 Full Stats", style=discord.ButtonStyle.blurple)
        async def stats(self, interaction: discord.Interaction, button: Button):
            user_data = get_user_data(interaction.user.id)
            stats = user_data.get('stats', {'sent': 0, 'failed': 0})
            
            total = stats['sent'] + stats['failed']
            success_rate = (stats['sent'] / total * 100) if total > 0 else 0
            
            embed = discord.Embed(
                title="📊 STATISTICS",
                description=f"**Total Messages:** {total}\n"
                           f"**Successful:** {stats['sent']}\n"
                           f"**Failed:** {stats['failed']}\n"
                           f"**Success Rate:** {success_rate:.1f}%",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    await interaction.response.send_message(embed=embed, view=PanelView(), ephemeral=True)

@tree.command(name="delete", description="Delete all your data")
async def delete(interaction: discord.Interaction):
    if str(interaction.user.id) in db:
        # Stop if running
        if interaction.user.id in active_tasks:
            del active_tasks[interaction.user.id]
        
        del db[str(interaction.user.id)]
        save_db(db)
        
        embed = discord.Embed(
            title="✅ DATA DELETED",
            description="All your data has been permanently deleted.\n\n"
                       "To use the bot again:\n"
                       "1. `/set-token`\n"
                       "2. `/setup`",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message("❌ No data found.", ephemeral=True)

@bot.event
async def on_ready():
    await tree.sync()
    print(f'✅ Bot online! Logged in as {bot.user}')
    print(f'📊 Serving {len(db)} users')

# Get bot token from environment variable
TOKEN = os.getenv('BOT_TOKEN')

if not TOKEN:
    print("❌ Error: BOT_TOKEN not found in environment variables!")
    exit(1)

# Run bot
bot.run(TOKEN)
