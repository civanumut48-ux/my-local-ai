"""
Cinnamon Roll AI
A friendly local assistant with a simple tkinter GUI, Jarvis-style commands, voice support,
file open/close, and reminder scheduling. 100% local, no internet API required.
"""

import ast
import datetime
import math
import random
import re
import textwrap
import threading
from pathlib import Path
import customtkinter as ctk
import tkinter.filedialog as filedialog
import tkinter.messagebox as messagebox

try:
    import pyttsx3
except ImportError:
    pyttsx3 = None

try:
    import speech_recognition as sr
except ImportError:
    sr = None

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

BOT_NAME = "Cinnamon Roll AI"
MEMORY_FILE = "cinnamon_roll_notes.txt"
REMINDERS_FILE = "cinnamon_roll_reminders.txt"

RESPONSES = {
    "greeting": [
        "Merhaba! Ben Cinnamon Roll AI. Sana bugün nasıl yardımcı olabilirim?",
        "Selam! Cinnamon Roll AI buradayım. Ne istersin?",
    ],
    "farewell": [
        "Görüşürüz! Umarım günün güzel geçer.",
        "Hoşça kal! Tatlı bir gün dilerim.",
    ],
    "thanks": [
        "Rica ederim! Her zaman yardımcı olmaktan mutluluk duyarım.",
        "Ne demek, ben buradayım!",
    ],
    "unknown": [
        "Bunu tam olarak anlayamadım, lütfen başka bir şekilde sorabilir misin?",
        "Ben daha çok yerel komutları anlarım. Farklı bir soru deneyebilirsin.",
    ],
    "how_are_you": [
        "Ben iyiyim, teşekkür ederim! Sen nasılsın?",
        "Enerjim yüksek, cinnamon roll gibi tatlı hissediyorum!",
    ],
    "cinnamon": [
        "Cinnamon roll mu? Harika seçim! Tatlı, sıcak ve her zaman mutlu eder.",
        "Cinnamon roll hayal ediyorum... ve bu bana yardımcı olma isteği veriyor!",
    ],
    "jarvis": [
        "Ben Cinnamon Roll AI'yım, Jarvis tarzı yerel bir asistanım.",
        "Jarvis gibi çalışıyorum ama tamamen yereldeyim, internete ihtiyaç yok.",
    ],
    "help": [
        "Şu komutları deneyebilirsin: saat kaç, tarih, hesapla 2+2, not al <metin>, hatırlat 5 dk sonra ...",
    ],
}

KEYWORDS = {
    "greeting": ["merhaba", "selam", "hey", "hello", "hi", "günaydın", "iyi akşamlar"],
    "farewell": ["bye", "görüşürüz", "çıkış", "hoşça", "güle güle"],
    "thanks": ["teşekkür", "sağol", "sağ ol", "thanks"],
    "how_are_you": ["nasılsın", "ne haber", "nasılsın?", "iyi misin"],
    "cinnamon": ["cinnamon", "roll", "tarçın", "tatlı"],
    "jarvis": ["jarvis", "j.a.r.v.i.s"],
    "help": ["yardım", "ne yapabilirsin", "komut"],
}

WRAP_WIDTH = 70
EXIT_COMMANDS = {"çıkış", "cikis", "bye", "quit", "exit"}


def format_message(text: str) -> str:
    return textwrap.fill(text, width=WRAP_WIDTH)


def choose_response(category: str) -> str:
    return random.choice(RESPONSES.get(category, RESPONSES["unknown"]))


def safe_eval_expression(expression: str) -> str:
    expression = expression.strip()
    if not expression:
        return "Hesaplanacak bir şey yok."

    # Türkçe "kök" komutunu parse et: "6 kök 8" → 6^(1/8)
    kök_match = re.search(r"(\d+\.?\d*)\s*kök\s*(\d+\.?\d*)", expression)
    if kök_match:
        base = float(kök_match.group(1))
        root = float(kök_match.group(2))
        try:
            if root == 0:
                return "Sıfırıncı kök hesaplanamaz."
            result = base ** (1 / root)
            return f"{base}^(1/{root}) = {result}"
        except Exception:
            return "Kök hesaplaması başarısız."

    # Trigonometrik ve matematiksel fonksiyonları ekle
    safe_dict = {
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "sqrt": math.sqrt,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
        "pi": math.pi,
        "e": math.e,
        "radians": math.radians,
        "degrees": math.degrees,
        "abs": abs,
        "pow": pow,
    }

    # Güvenlik: sadece izin verilen karakterleri kullan
    if not re.fullmatch(r"[0-9+\-*/().\s,a-z_]+", expression.lower()):
        return "Üzgünüm, sadece sayılar ve temel matematik işlemleri destekliyorum."

    try:
        node = ast.parse(expression, mode="eval")
        for subnode in ast.walk(node):
            if isinstance(subnode, (ast.Call, ast.Name, ast.Attribute, ast.Subscript, ast.Import, ast.ImportFrom)):
                # İzin verilen fonksiyonları kontrol et
                if isinstance(subnode, ast.Name) and subnode.id not in safe_dict and subnode.id not in "pi e":
                    continue
                if isinstance(subnode, ast.Call) and isinstance(subnode.func, ast.Name):
                    if subnode.func.id not in safe_dict:
                        return f"'{subnode.func.id}' fonksiyonunu desteklemiyorum."
                elif isinstance(subnode, (ast.Import, ast.ImportFrom)):
                    return "İthalatı desteklemiyorum."
        
        result = eval(compile(node, filename="<ast>", mode="eval"), {"__builtins__": {}, **safe_dict})
        return str(result)
    except ZeroDivisionError:
        return "Sıfıra bölünemez!"
    except ValueError as e:
        return f"Hesaplama hatası: {str(e)}"
    except Exception as e:
        return "İfadeyi anlayamadım. Lütfen geçerli bir hesaplama gir."


def save_note(text: str) -> str:
    try:
        with open(MEMORY_FILE, "a", encoding="utf-8") as file:
            file.write(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {text}\n")
        return "Notun kaydedildi."
    except OSError:
        return "Not kaydedilirken bir hata oluştu."


def save_reminder_entry(delay_seconds: int, text: str) -> None:
    try:
        with open(REMINDERS_FILE, "a", encoding="utf-8") as file:
            file.write(f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} +{delay_seconds}s - {text}\n")
    except OSError:
        pass


def parse_reminder_command(user_text: str) -> tuple:
    lower = user_text.lower()
    reminder_text = user_text
    if lower.startswith("hatırlatıcı kur"):
        reminder_text = user_text[len("hatırlatıcı kur"):].strip()
    elif lower.startswith("hatırlat"):
        reminder_text = user_text[len("hatırlat"):].strip()

    match = re.search(r"(\d+)\s*(saniye|sn|dakika|dk|saat|sa)\b", reminder_text, flags=re.IGNORECASE)
    if not match:
        return None, None

    amount = int(match.group(1))
    unit = match.group(2).lower()
    if unit in {"saniye", "sn"}:
        delay = amount
    elif unit in {"dakika", "dk"}:
        delay = amount * 60
    else:
        delay = amount * 3600

    remainder = reminder_text[match.end():].strip()
    remainder = re.sub(r"^sonra\b", "", remainder, flags=re.IGNORECASE).strip()
    if not remainder:
        remainder = "Hatırlatma zamanı geldi."

    return delay, remainder


def get_response(user_text: str) -> str:
    lower_text = user_text.lower().strip()

    if lower_text in EXIT_COMMANDS:
        return choose_response("farewell")

    if lower_text.startswith("hesapla"):
        expression = lower_text.replace("hesapla", "", 1).strip()
        result = safe_eval_expression(expression)
        return f"Hesaplama sonucu: {result}"

    if "saat" in lower_text:
        return datetime.datetime.now().strftime("Şu an saat %H:%M.")

    if "tarih" in lower_text:
        return datetime.datetime.now().strftime("Bugün %d.%m.%Y.")

    if lower_text.startswith("not al"):
        note = user_text[len("not al"):].strip()
        if not note:
            return "Lütfen kaydetmek istediğin notu yaz."
        return save_note(note)

    if lower_text.startswith("not tut"):
        note = user_text[len("not tut"):].strip()
        if not note:
            return "Lütfen kaydetmek istediğin notu yaz."
        return save_note(note)

    for category, words in KEYWORDS.items():
        for word in words:
            if word in lower_text:
                return choose_response(category)

    return choose_response("unknown")


class ReminderManager:
    def __init__(self):
        self.timers = []

    def schedule(self, delay, text, callback):
        timer = threading.Timer(delay, callback, args=(text,))
        timer.daemon = True
        timer.start()
        self.timers.append(timer)


class CinnamonRollAIApp:
    def __init__(self, root):
        self.root = root
        self.root.title(BOT_NAME)
        self.root.geometry("700x550")
        self.root.resizable(False, False)
        self.opened_file_path = None
        self.last_bot_message = ""
        self.reminder_manager = ReminderManager()

        self.voice_engine = pyttsx3.init() if pyttsx3 else None
        if self.voice_engine is not None:
            self.voice_engine.setProperty("rate", 160)

        self.recognizer = None
        self.microphone = None
        if sr is not None:
            try:
                self.recognizer = sr.Recognizer()
                self.microphone = sr.Microphone()
            except Exception:
                self.recognizer = None
                self.microphone = None

        # Main container frame
        main_frame = ctk.CTkFrame(self.root)
        main_frame.pack(fill="both", expand=True, padx=0, pady=0)

        # Title label
        title_label = ctk.CTkLabel(
            main_frame,
            text="🤖 CINNAMON ROLL AI",
            font=("Courier New", 16, "bold"),
            text_color="#00d4ff"
        )
        title_label.pack(pady=(12, 8))

        # Chat area with custom styling
        self.chat_area = ctk.CTkTextbox(
            main_frame,
            wrap="word",
            font=("Consolas", 10),
            text_color="#e0e0e0",
            fg_color="#0a0e27",
            border_color="#00d4ff",
            border_width=1
        )
        self.chat_area.pack(padx=12, pady=(0, 12), fill="both", expand=True)

        # Entry frame
        entry_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        entry_frame.pack(fill="x", padx=12, pady=(0, 12))

        self.user_entry = ctk.CTkEntry(
            entry_frame,
            font=("Segoe UI", 11),
            placeholder_text="Komutunuzu yazınız...",
            text_color="#e0e0e0",
            fg_color="#0f1535",
            border_color="#00d4ff",
            border_width=1
        )
        self.user_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.user_entry.bind("<Return>", self.on_send)

        send_button = ctk.CTkButton(
            entry_frame,
            text="Gönder",
            width=80,
            command=self.on_send,
            fg_color="#00d4ff",
            hover_color="#0099cc",
            text_color="#000000",
            font=("Segoe UI", 10, "bold")
        )
        send_button.pack(side="right")

        # Button frame 1
        button_frame1 = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame1.pack(fill="x", padx=12, pady=(0, 6))

        self.voice_button = ctk.CTkButton(
            button_frame1,
            text="🎤 Sesli Komut",
            width=130,
            command=self.listen_voice_command,
            fg_color="#1a3a52",
            hover_color="#2a5a7f",
            text_color="#00d4ff",
            font=("Segoe UI", 9)
        )
        self.voice_button.pack(side="left", padx=(0, 6))

        self.speak_button = ctk.CTkButton(
            button_frame1,
            text="🔊 Sesle Cevap",
            width=130,
            command=self.speak_latest_message,
            fg_color="#1a3a52",
            hover_color="#2a5a7f",
            text_color="#00d4ff",
            font=("Segoe UI", 9)
        )
        self.speak_button.pack(side="left", padx=(0, 6))

        self.open_button = ctk.CTkButton(
            button_frame1,
            text="📁 Dosya Aç",
            width=110,
            command=self.open_file,
            fg_color="#1a3a52",
            hover_color="#2a5a7f",
            text_color="#00d4ff",
            font=("Segoe UI", 9)
        )
        self.open_button.pack(side="left", padx=(0, 6))

        self.close_button = ctk.CTkButton(
            button_frame1,
            text="📴 Dosya Kapat",
            width=110,
            command=self.close_file_button,
            fg_color="#1a3a52",
            hover_color="#2a5a7f",
            text_color="#00d4ff",
            font=("Segoe UI", 9)
        )
        self.close_button.pack(side="left")

        # Button frame 2 (Exit on right)
        button_frame2 = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame2.pack(fill="x", padx=12, pady=(0, 12))

        self.exit_button = ctk.CTkButton(
            button_frame2,
            text="❌ Çıkış",
            width=80,
            command=self.root.quit,
            fg_color="#8b0000",
            hover_color="#cc0000",
            text_color="#ffffff",
            font=("Segoe UI", 9, "bold")
        )
        self.exit_button.pack(side="right")

        self.show_welcome_message()

    def append_chat(self, speaker, text):
        self.chat_area.insert("end", f"{speaker}: {text}\n\n")
        self.chat_area.see("end")
        if speaker == BOT_NAME:
            self.last_bot_message = text

    def show_welcome_message(self):
        welcome = (
            "Merhaba! Cinnamon Roll AI'ye hoş geldin."
            " Beni Jarvis tarzı yerel asistanın olarak kullanabilirsin."
            " Sesli komut için 'Sesli Komut' düğmesine bas, dosya aç/kapat için ilgili düğmelere bas,"
            " hatırlatma kurmak için 'hatırlat 5 dk sonra ...' yazabilirsin."
        )
        self.append_chat(BOT_NAME, format_message(welcome))

    def on_send(self, event=None):
        user_text = self.user_entry.get().strip()
        if not user_text:
            return

        self.append_chat("Sen", user_text)
        self.user_entry.delete(0, "end")

        if user_text.lower().strip() in EXIT_COMMANDS:
            self.append_chat(BOT_NAME, choose_response("farewell"))
            self.root.after(500, self.root.quit)
            return

        command_result = self.process_command(user_text)
        if command_result is not None:
            self.append_chat(BOT_NAME, format_message(command_result))
            return

        bot_reply = get_response(user_text)
        self.append_chat(BOT_NAME, format_message(bot_reply))

    def process_command(self, user_text):
        lower_text = user_text.lower().strip()

        if any(key in lower_text for key in ["dosya aç", "dosya ac", "open file"]):
            self.open_file()
            return None

        if any(key in lower_text for key in ["dosya kapa", "dosya kapat", "close file"]):
            return self.close_file()

        if "hatırlat" in lower_text or "hatırlatıcı" in lower_text:
            delay, message = parse_reminder_command(user_text)
            if delay is None:
                return "Lütfen hatırlatma için zaman belirt. Örnek: hatırlat 5 dk sonra çay iç."
            self.reminder_manager.schedule(delay, message, self.reminder_alert)
            save_reminder_entry(delay, message)
            return f"Hatırlatıcı ayarlandı: {delay} saniye sonra '{message}'."

        if any(key in lower_text for key in ["sesli komut", "ses komutu"]):
            self.listen_voice_command()
            return "Sesli komut dinleniyor; lütfen konuşun."

        if any(key in lower_text for key in ["sesle", "konuş", "speak", "ses"]):
            self.speak_latest_message()
            return None

        if any(key in lower_text for key in ["yardım", "ne yapabilirsin", "komut"]):
            return choose_response("help")

        return None

    def open_file(self):
        file_path = filedialog.askopenfilename(
            title="Dosya Aç",
            defaultextension="*.*",
            filetypes=[("Text files", "*.txt"), ("Python files", "*.py"), ("All files", "*.*")],
        )
        if not file_path:
            self.append_chat(BOT_NAME, "Dosya seçilmedi.")
            return

        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = Path(file_path).read_text(encoding="cp1254", errors="replace")

        self.opened_file_path = file_path
        preview_lines = content.splitlines()[:20]
        preview = "\n".join(preview_lines)
        if len(content.splitlines()) > 20:
            preview += "\n... (dosya içeriği kısaltıldı)"

        self.append_chat(BOT_NAME, f"Dosya açıldı: {file_path}\n{preview}")

    def close_file(self):
        if not self.opened_file_path:
            return "Şu anda açık bir dosya yok."

        self.opened_file_path = None
        return "Açık dosya kapatıldı."

    def close_file_button(self):
        result = self.close_file()
        self.append_chat(BOT_NAME, result)

    def speak_latest_message(self):
        if self.voice_engine is None:
            self.append_chat(BOT_NAME, "Sesli yanıt için pyttsx3 kütüphanesi yok. pip install pyttsx3 yükleyebilirsin.")
            return

        if not self.last_bot_message:
            self.append_chat(BOT_NAME, "Henüz okunacak bir yanıt yok.")
            return

        self.append_chat(BOT_NAME, f"[Sesle] {self.last_bot_message}")
        threading.Thread(target=self._run_voice, args=(self.last_bot_message,), daemon=True).start()

    def _run_voice(self, text):
        try:
            self.voice_engine.say(text)
            self.voice_engine.runAndWait()
        except Exception:
            self.root.after(0, lambda: self.append_chat(BOT_NAME, "Sesli yanıt sırasında bir hata oluştu."))

    def listen_voice_command(self):
        if sr is None:
            self.append_chat(BOT_NAME, "Sesli komut için SpeechRecognition kütüphanesi yok. pip install SpeechRecognition yükleyebilirsin.")
            return
        if self.recognizer is None or self.microphone is None:
            self.append_chat(BOT_NAME, "Mikrofon veya ses tanıma aracı yapılandırılamadı.")
            return

        threading.Thread(target=self._listen_in_background, daemon=True).start()

    def _listen_in_background(self):
        try:
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=8)
            text = self.recognizer.recognize_sphinx(audio)
            self.root.after(0, lambda: self.handle_voice_text(text))
        except sr.UnknownValueError:
            self.root.after(0, lambda: self.append_chat(BOT_NAME, "Seni anlayamadım. Lütfen tekrar dene."))
        except sr.RequestError as error:
            self.root.after(0, lambda: self.append_chat(BOT_NAME, f"Ses tanıma hatası: {error}"))
        except Exception as error:
            self.root.after(0, lambda: self.append_chat(BOT_NAME, f"Sesli komut çalıştırılamadı: {error}"))

    def handle_voice_text(self, text):
        self.append_chat("Ses", text)
        command_result = self.process_command(text)
        if command_result is not None:
            self.append_chat(BOT_NAME, format_message(command_result))
            return

        bot_reply = get_response(text)
        self.append_chat(BOT_NAME, format_message(bot_reply))

    def reminder_alert(self, message):
        self.root.after(0, lambda: self.append_chat(BOT_NAME, f"Hatırlatma: {message}"))


def main():
    root = ctk.CTk()
    app = CinnamonRollAIApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
