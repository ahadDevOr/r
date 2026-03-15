import os
import asyncio
import threading
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!", 200

@app.route('/health')
def health():
    return "OK", 200

def run_bot():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def start_app():
        from database import init_db
        init_db()

        import os
        from telegram.ext import (
            Application, CommandHandler, MessageHandler,
            CallbackQueryHandler, ConversationHandler, filters
        )
        from main import (
            start, create_start, got_token, got_name, cancel,
            my_bots_show, bot_menu, bot_action, confirm_delete,
            main_cb, load_saved_bots, ASK_TOKEN, ASK_NAME, MAIN_BOT_TOKEN
        )

        application = Application.builder().token(MAIN_BOT_TOKEN).build()

        conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(create_start, pattern='^m:create$')],
            states={
                ASK_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_token)],
                ASK_NAME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, got_name)],
            },
            fallbacks=[CommandHandler('cancel', cancel)],
        )

        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("mybots", lambda u,c: my_bots_show(u,c)))
        application.add_handler(conv)
        application.add_handler(CallbackQueryHandler(main_cb,        pattern=r'^m:'))
        application.add_handler(CallbackQueryHandler(bot_menu,       pattern=r'^bm:'))
        application.add_handler(CallbackQueryHandler(bot_action,     pattern=r'^ba:'))
        application.add_handler(CallbackQueryHandler(confirm_delete, pattern=r'^bx:'))

        async def post_init(app):
            await load_saved_bots(app)

        application.post_init = post_init

        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)
        await asyncio.Event().wait()

    loop.run_until_complete(start_app())

bot_thread = threading.Thread(target=run_bot, daemon=True)
bot_thread.start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
        
