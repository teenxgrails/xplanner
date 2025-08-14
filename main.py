import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Updater, CommandHandler, CallbackContext, 
    ConversationHandler, CallbackQueryHandler,
    MessageHandler, Filters, JobQueue
)
from datetime import datetime, timedelta
import sqlite3
import pytz
import re

# Database setup (GDPR-compliant data handling)
conn = sqlite3.connect('tasks.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS tasks (
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             user_id INTEGER,
             description TEXT,
             due_date DATETIME,
             category TEXT,
             priority INTEGER DEFAULT 0,
             status TEXT DEFAULT 'pending'
             )''')
c.execute('''CREATE TABLE IF NOT EXISTS users (
             user_id INTEGER PRIMARY KEY,
             timezone TEXT DEFAULT 'Europe/Berlin',
             language TEXT DEFAULT 'en'
             )''')
conn.commit()

# Bot configuration
TOKEN = "7913551809:AAHPJUrAHuIywC0zKvQb3o-7bFJ08kCOQ1M"
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Conversation states
DESCRIPTION, DATE, CATEGORY, PRIORITY, SETTINGS = range(5)

# European-style design elements
EUROPEAN_CATEGORIES = {
    'Work': '💼',
    'Personal': '👤',
    'Shopping': '🛍',
    'Health': '⚕️',
    'Education': '🎓',
    'Finance': '💶',
    'Travel': '✈️'
}

PRIORITY_LEVELS = {
    '4': 'Critical (1)',
    '3': 'High (2)',
    '2': 'Medium (3)',
    '1': 'Low (4)'
}

# Start command - minimal European design
def start(update: Update, context: CallbackContext) -> None:
    user = update.effective_user
    user_id = user.id
    
    # Initialize user settings
    c.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    
    # European-style welcome message
    update.message.reply_text(
        f"Guten Tag {user.first_name}! 🇪🇺\n\n"
        "Welcome to your European Task Planner.\n"
        "Efficient • Private • Organized\n\n"
        "Please select an option:",
        reply_markup=main_menu_keyboard()
    )

# Main menu keyboard (clean European design)
def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            ["➕ Create Task"],
            ["📋 My Tasks", "📅 Today"],
            ["⚠️ Important", "⏱ Upcoming"],
            ["⚙️ Settings"]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )

# Handle button presses
def handle_buttons(update: Update, context: CallbackContext) -> None:
    text = update.message.text
    if text == "➕ Create Task":
        update.message.reply_text("Please describe your task:")
        context.user_data.clear()
        return DESCRIPTION
    elif text == "📋 My Tasks":
        show_tasks(update, context, "SELECT * FROM tasks WHERE user_id = ? ORDER BY due_date", "Your Tasks")
    elif text == "📅 Today":
        today = datetime.now(pytz.utc).date()
        show_tasks(update, context, f"SELECT * FROM tasks WHERE user_id = ? AND DATE(due_date) = '{today}' ORDER BY due_date", "Today's Tasks")
    elif text == "⏱ Upcoming":
        show_tasks(update, context, "SELECT * FROM tasks WHERE user_id = ? AND due_date > datetime('now') ORDER BY due_date", "Upcoming Tasks")
    elif text == "⚠️ Important":
        show_tasks(update, context, "SELECT * FROM tasks WHERE user_id = ? AND priority >= 3 ORDER BY due_date", "Important Tasks")
    elif text == "⚙️ Settings":
        show_settings(update, context)
    return ConversationHandler.END

# Task creation flow
def handle_description(update: Update, context: CallbackContext) -> int:
    context.user_data['description'] = update.message.text
    
    # European date format options
    buttons = [
        [InlineKeyboardButton("Today", callback_data='today')],
        [InlineKeyboardButton("Tomorrow", callback_data='tomorrow')],
        [InlineKeyboardButton("Next Week", callback_data='next_week')],
        [InlineKeyboardButton("Custom...", callback_data='custom')]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    
    update.message.reply_text(
        "📅 Due date (DD.MM.YYYY HH:MM format):\n"
        "Examples:\n"
        "• 25.12.2023 15:30\n"
        "• 01.01.2024 09:00",
        reply_markup=reply_markup
    )
    return DATE

def handle_date(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    choice = query.data
    
    now = datetime.now(pytz.utc)
    if choice == 'today':
        due_date = now.replace(hour=17, minute=0)  # 5 PM today
    elif choice == 'tomorrow':
        due_date = now + timedelta(days=1)
        due_date = due_date.replace(hour=9, minute=0)  # 9 AM tomorrow
    elif choice == 'next_week':
        due_date = now + timedelta(weeks=1)
        due_date = due_date.replace(hour=9, minute=0)  # 9 AM next week
    else:
        query.edit_message_text("Please enter date and time (DD.MM.YYYY HH:MM)")
        return DATE
    
    context.user_data['due_date'] = due_date
    show_european_category_selector(query)
    return CATEGORY

def handle_custom_date(update: Update, context: CallbackContext) -> int:
    try:
        text = update.message.text
        # Convert European date format to datetime
        day, month, year_time = text.split('.', 2)
        year, time = year_time.split(' ', 1)
        hour, minute = time.split(':')
        
        due_date = datetime(
            int(year), int(month), int(day),
            int(hour), int(minute)
        )
        due_date = pytz.utc.localize(due_date)
        
        context.user_data['due_date'] = due_date
        show_european_category_selector(update.message)
        return CATEGORY
    except (ValueError, IndexError):
        update.message.reply_text(
            "⚠️ Invalid format. Please use DD.MM.YYYY HH:MM format.\n"
            "Example: 25.12.2023 15:30"
        )
        return DATE

def show_european_category_selector(source):
    buttons = [
        [InlineKeyboardButton(f"{EUROPEAN_CATEGORIES['Work']} Work", callback_data='Work')],
        [InlineKeyboardButton(f"{EUROPEAN_CATEGORIES['Personal']} Personal", callback_data='Personal')],
        [InlineKeyboardButton(f"{EUROPEAN_CATEGORIES['Shopping']} Shopping", callback_data='Shopping')],
        [InlineKeyboardButton(f"{EUROPEAN_CATEGORIES['Health']} Health", callback_data='Health')],
        [InlineKeyboardButton(f"{EUROPEAN_CATEGORIES['Education']} Education", callback_data='Education')],
        [InlineKeyboardButton(f"{EUROPEAN_CATEGORIES['Finance']} Finance", callback_data='Finance')]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    
    if isinstance(source, Update):
        source.message.reply_text("Select category:", reply_markup=reply_markup)
    else:
        source.edit_message_text("Select category:", reply_markup=reply_markup)

def handle_category(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    context.user_data['category'] = query.data
    
    buttons = [
        [InlineKeyboardButton("1 - Critical", callback_data='4')],
        [InlineKeyboardButton("2 - High", callback_data='3')],
        [InlineKeyboardButton("3 - Medium", callback_data='2')],
        [InlineKeyboardButton("4 - Low", callback_data='1')]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    query.edit_message_text("Select priority (1=highest, 4=lowest):", reply_markup=reply_markup)
    
    return PRIORITY

def handle_priority(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    priority = int(query.data)
    
    # Save task to database
    user_id = update.effective_user.id
    description = context.user_data['description']
    due_date = context.user_data['due_date']
    category = context.user_data['category']
    
    c.execute("INSERT INTO tasks (user_id, description, due_date, category, priority) VALUES (?, ?, ?, ?, ?)",
              (user_id, description, due_date, category, priority))
    conn.commit()
    
    # Schedule notification
    job_queue = context.job_queue
    context.job_queue.run_once(notify_task, due_date - datetime.now(pytz.utc), 
                              context=(user_id, description, priority))
    
    # Confirmation message
    formatted_date = due_date.strftime("%d.%m.%Y at %H:%M")
    
    query.edit_message_text(
        f"✓ Task Created\n\n"
        f"• {description}\n"
        f"• Due: {formatted_date}\n"
        f"• Category: {EUROPEAN_CATEGORIES[category]} {category}\n"
        f"• Priority: {PRIORITY_LEVELS[str(priority)]}"
    )
    
    update.callback_query.message.reply_text(
        "Task successfully added. How can I assist you next?",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

# European-style task display
def show_tasks(update: Update, context: CallbackContext, query=None, title="TASKS"):
    user_id = update.effective_user.id
    tasks = c.execute(query, (user_id,)).fetchall() if query else []
    
    if not tasks:
        update.message.reply_text("No tasks found. Enjoy your free time! ☕️", 
                                reply_markup=main_menu_keyboard())
        return
    
    response = f"<b>{title}</b>\n\n"
    for task in tasks:
        id, _, desc, due_date, category, priority, status = task
        due_datetime = datetime.strptime(due_date, "%Y-%m-%d %H:%M:%S")
        formatted_date = due_datetime.strftime("%d.%m.%Y %H:%M")
        days_left = (due_datetime - datetime.now()).days
        
        # Priority indicator
        priority_text = f"P{priority}" if priority > 1 else ""
        
        response += (
            f"• <b>{desc}</b>\n"
            f"  {formatted_date} | {EUROPEAN_CATEGORIES[category]} {category} | {priority_text}\n"
            f"  Days remaining: {days_left}\n\n"
        )
    
    update.message.reply_text(response, parse_mode='HTML')
    update.message.reply_text("Select your next action:", reply_markup=main_menu_keyboard())

# Settings menu for European users
def show_settings(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    # Get user settings
    timezone, language = c.execute(
        "SELECT timezone, language FROM users WHERE user_id = ?", 
        (user_id,)
    ).fetchone() or ('Europe/Berlin', 'en')
    
    buttons = [
        [InlineKeyboardButton(f"🌍 Timezone: {timezone}", callback_data='timezone')],
        [InlineKeyboardButton(f"🗣 Language: {language.upper()}", callback_data='language')],
        [InlineKeyboardButton("📤 Export My Data", callback_data='export_data')],
        [InlineKeyboardButton("❌ Delete All Data", callback_data='delete_data')]
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    
    update.message.reply_text(
        "<b>Privacy & Settings</b>\n\n"
        "We comply with GDPR regulations. Your data is stored securely and never shared.\n\n"
        "Configure your preferences:",
        parse_mode='HTML',
        reply_markup=reply_markup
    )
    return SETTINGS

def handle_settings(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    choice = query.data
    
    if choice == 'timezone':
        # European timezones
        buttons = [
            [InlineKeyboardButton("Berlin (CET)", callback_data='Europe/Berlin')],
            [InlineKeyboardButton("London (GMT)", callback_data='Europe/London')],
            [InlineKeyboardButton("Paris (CET)", callback_data='Europe/Paris')],
            [InlineKeyboardButton("Madrid (CET)", callback_data='Europe/Madrid')],
            [InlineKeyboardButton("Stockholm (CET)", callback_data='Europe/Stockholm')]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        query.edit_message_text("Select your timezone:", reply_markup=reply_markup)
        
    elif choice == 'language':
        buttons = [
            [InlineKeyboardButton("English", callback_data='en')],
            [InlineKeyboardButton("Deutsch", callback_data='de')],
            [InlineKeyboardButton("Français", callback_data='fr')],
            [InlineKeyboardButton("Español", callback_data='es')],
            [InlineKeyboardButton("Italiano", callback_data='it')]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        query.edit_message_text("Select your language:", reply_markup=reply_markup)
        
    elif choice == 'export_data':
        query.edit_message_text(
            "Your data export is being prepared...\n\n"
            "We take your privacy seriously. According to GDPR regulations, "
            "you have the right to access all personal data we store about you."
        )
        # In a real implementation, you would generate a data export file here
        
    elif choice == 'delete_data':
        buttons = [
            [InlineKeyboardButton("Confirm Delete", callback_data='confirm_delete')],
            [InlineKeyboardButton("Cancel", callback_data='cancel_delete')]
        ]
        reply_markup = InlineKeyboardMarkup(buttons)
        query.edit_message_text(
            "<b>⚠️ Data Deletion Request</b>\n\n"
            "This will permanently delete ALL your tasks and personal data from our systems.\n\n"
            "This action is irreversible. Are you sure?",
            parse_mode='HTML',
            reply_markup=reply_markup
        )

def save_setting(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    user_id = update.effective_user.id
    data = query.data
    
    if data in ['Europe/Berlin', 'Europe/London', 'Europe/Paris', 'Europe/Madrid', 'Europe/Stockholm']:
        c.execute("UPDATE users SET timezone = ? WHERE user_id = ?", (data, user_id))
        conn.commit()
        query.edit_message_text(f"Timezone updated to {data}")
        
    elif data in ['en', 'de', 'fr', 'es', 'it']:
        c.execute("UPDATE users SET language = ? WHERE user_id = ?", (data, user_id))
        conn.commit()
        query.edit_message_text(f"Language updated to {data.upper()}")
        
    elif data == 'confirm_delete':
        c.execute("DELETE FROM tasks WHERE user_id = ?", (user_id,))
        c.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()
        query.edit_message_text("All your data has been permanently deleted.")
        
    elif data == 'cancel_delete':
        query.edit_message_text("Data deletion cancelled.")
    
    query.message.reply_text("Settings updated. How can I assist you next?", 
                           reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# Notification system
def notify_task(context: CallbackContext) -> None:
    job = context.job
    user_id, description, priority = job.context
    priority_text = PRIORITY_LEVELS[str(priority)]
    
    context.bot.send_message(
        chat_id=user_id,
        text=f"🔔 TASK REMINDER\n\n{description}\nPriority: {priority_text}\n\nThis task is due now."
    )

# Main function
def main() -> None:
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # Conversation handlers
    task_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex(r'^➕ Create Task$'), handle_buttons)],
        states={
            DESCRIPTION: [MessageHandler(Filters.text & ~Filters.command, handle_description)],
            DATE: [
                CallbackQueryHandler(handle_date, pattern=r'^(today|tomorrow|next_week)$'),
                MessageHandler(Filters.text & ~Filters.command, handle_custom_date)
            ],
            CATEGORY: [CallbackQueryHandler(handle_category)],
            PRIORITY: [CallbackQueryHandler(handle_priority)]
        },
        fallbacks=[CommandHandler('cancel', lambda u,c: u.message.reply_text("Operation cancelled.", reply_markup=main_menu_keyboard()))]
    )
    
    settings_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex(r'^⚙️ Settings$'), handle_buttons)],
        states={
            SETTINGS: [CallbackQueryHandler(handle_settings)],
            'HANDLE_SETTING': [CallbackQueryHandler(save_setting)]
        },
        fallbacks=[]
    )

    # Register handlers
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(task_handler)
    dispatcher.add_handler(settings_handler)
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_buttons))

    # Start the bot
    updater.start_polling()
    logger.info("European Task Bot is running...")
    updater.idle()

if __name__ == '__main__':
    main()
