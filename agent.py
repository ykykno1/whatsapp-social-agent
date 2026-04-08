"""
agent.py - לוגיקת הסוכן החכם
"""
import re
import os
import anthropic
from database import (
    get_client, get_all_clients, add_client,
    get_conversation_history, save_message, clear_conversation_history
)

client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-haiku-4-5"
MAX_TOKENS = 1024

SYSTEM_PROMPT = """אתה עוזר אישי חכם ומקצועי למנהל/ת סושיאל מדיה.
תפקידך לעזור ביצירת תוכן איכותי, כתיבת פוסטים, סקריפטים וקפשנים עבור לקוחות שונים.

כללים:
1. תמיד כתוב בעברית אלא אם התבקשת אחרת
2. התאם את הסגנון לפרופיל הלקוח הרלוונטי
3. היה יצירתי, מעניין ומשפיע
4. פוסטים - סיים עם 5-8 האשטגים
5. סקריפטים - חלק לסצנות ברורות
6. לקוח לא במערכת - הודע בנחמדות

פקודות:
- פוסט ל[לקוח] על [נושא]
- סקריפט ל[לקוח] ל-[פלטפורמה]
- קפשן ל[לקוח]
- הוסף לקוח [שם]
- לקוחות
- נקה היסטוריה"""

def build_client_context(client_name):
    data = get_client(client_name)
    if not data:
        return f"⚠️ לקוח '{client_name}' לא נמצא. הוסף עם: הוסף לקוח {client_name}"
    forbidden = ", ".join(data["forbidden_topics"]) or "אין"
    days = ", ".join(data["preferred_posting_days"])
    return f"""מידע על '{client_name}':
- טון: {data['tone']}
- קהל יעד: {data['target_audience']}
- נושאים אסורים: {forbidden}
- ימי פרסום: {days}
- מידע נוסף: {data['extra_info'] or 'אין'}"""

def detect_command(message):
    message = message.strip()
    m = re.match(r'פוסט ל(.+?) על (.+)', message, re.IGNORECASE)
    if m:
        return "post", {"client": m.group(1).strip(), "topic": m.group(2).strip()}
    m = re.match(r'סקריפט ל(.+?) ל-?(.+)', message, re.IGNORECASE)
    if m:
        return "script", {"client": m.group(1).strip(), "platform": m.group(2).strip()}
    m = re.match(r'קפשן ל(.+)', message, re.IGNORECASE)
    if m:
        return "caption", {"client": m.group(1).strip()}
    m = re.match(r'הוסף לקוח (.+)', message, re.IGNORECASE)
    if m:
        return "add_client", {"name": m.group(1).strip()}
    if message in ["לקוחות", "רשימת לקוחות", "הצג לקוחות"]:
        return "list_clients", {}
    if message in ["נקה היסטוריה", "מחק היסטוריה", "התחל מחדש"]:
        return "clear_history", {}
    return None, None

def handle_add_client(name):
    if get_client(name):
        return f"ℹ️ לקוח '{name}' כבר קיים."
    if add_client(name):
        return (f"✅ לקוח '{name}' נוסף!\n\n"
                f"שלח לי:\n• טון/סגנון\n• קהל יעד\n• נושאים אסורים\n• ימי פרסום")
    return "❌ שגיאה בהוספת הלקוח."

def handle_list_clients():
    clients = get_all_clients()
    if not clients:
        return "📋 אין לקוחות עדיין.\nהוסף עם: הוסף לקוח [שם]"
    lines = ["📋 *הלקוחות שלך:*\n"]
    for i, c in enumerate(clients, 1):
        lines.append(f"{i}. *{c['name']}* - {c['tone']}")
    lines.append(f"\nסה\"כ: {len(clients)}")
    return "\n".join(lines)

def build_enhanced_prompt(command_type, params):
    ctx = build_client_context(params.get("client", ""))
    if "⚠️" in ctx:
        return ctx
    if command_type == "post":
        return f"{ctx}\n\nכתוב פוסט על: {params['topic']}\n3-5 משפטים, CTA ברור, 5-8 האשטגים."
    elif command_type == "script":
        return f"{ctx}\n\nסקריפט וידאו ל-{params['platform']}.\nפתיחה חזקה (3 שניות), גוף (30-45 שניות), CTA בסוף. חלק לסצנות."
    elif command_type == "caption":
        return f"{ctx}\n\nכתוב קפשן אפקטיבי.\nשורה ראשונה מושכת, תיאור ויזואל, שאלה למעורבות, 3-5 האשטגים."
    return ""

def process_message(phone_number, message):
    message = message.strip()
    if not message:
        return "שלום! אני כאן לעזור 😊"

    command_type, params = detect_command(message)

    if command_type == "add_client":
        return handle_add_client(params["name"])
    if command_type == "list_clients":
        return handle_list_clients()
    if command_type == "clear_history":
        count = clear_conversation_history(phone_number)
        return f"🗑️ נמחקו {count} הודעות. נתחיל מחדש!"

    enhanced = message
    if command_type in ("post", "script", "caption"):
        enhanced = build_enhanced_prompt(command_type, params)
        if "⚠️" in enhanced:
            return enhanced

    save_message(phone_number, "user", message)
    history = get_conversation_history(phone_number, limit=20)
    messages_api = history[:-1]
    messages_api.append({"role": "user", "content": enhanced})

    try:
        response = client.messages.create(
            model=MODEL, max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT, messages=messages_api
        )
        reply = response.content[0].text
        save_message(phone_number, "assistant", reply)
        return reply
    except anthropic.APIConnectionError:
        return "❌ שגיאת חיבור. נסה שוב."
    except anthropic.RateLimitError:
        return "⏳ עומס, נסה שוב בעוד שניות."
    except Exception as e:
        return f"❌ שגיאה: {str(e)}"
