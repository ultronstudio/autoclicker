import json
import locale
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox
import webbrowser
import threading
import time
import random

import pyautogui
from pynput import keyboard

# constants
ICON_PATH = "icon.ico"
NAME = "Nano Auto Clicker"


def get_version():
    env_version = os.getenv("NANOCLICKER_VERSION")
    if env_version:
        return env_version.strip().lstrip("v")

    return "canary"


VERSION = get_version()
VERSIONED_NAME = f"{NAME} {VERSION}"

DONATE_NAME = "Petr Vurm"
DONATE_IBAN = "CZ46 0800 0000 0070 3051 4389"
DONATE_ACCOUNT = "7030514389/0800"
DONATE_EMAIL = "kontakt@petrvurm.cz"
DONATE_CAMPAIGNS_URL = "https://kampane.petrvurm.cz/"


def get_app_base_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def detect_language():
    override = os.getenv("NANOCLICKER_LANG")
    if override:
        return override.lower()

    current = (locale.getdefaultlocale()[0] or "").lower()
    return "cs" if current.startswith("cs") else "en"


def load_translations():
    lang_code = detect_language()
    file_path = get_app_base_dir() / "lang" / f"{lang_code}.json"

    if not file_path.exists():
        file_path = get_app_base_dir() / "lang" / "en.json"

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

class NanoAutoClicker:
    def __init__(self, root):
        self.root = root
        self.root.title(VERSIONED_NAME)
        self.root.geometry("760x600")
        self.root.minsize(760, 600)
        self.root.resizable(False, False)

        # icon
        try:
            self.root.iconbitmap(ICON_PATH)
        except Exception:
            pass

        self.root.attributes("-topmost", True)
        self.root.bind("<Unmap>", self.on_window_minimize)
        self.root.bind("<Map>", self.on_window_restore)

        self.running = False
        self.click_thread = None
        self.listener = None

        self.mouse_button = tk.StringVar(value="Left")
        self.click_type = tk.StringVar(value="Single")

        self.hours_var = tk.StringVar(value="0")
        self.minutes_var = tk.StringVar(value="0")
        self.seconds_var = tk.StringVar(value="0")
        self.milliseconds_var = tk.StringVar(value="1")
        self.nanoseconds_var = tk.StringVar(value="0")

        self.random_enabled = tk.BooleanVar(value=False)
        self.random_offset_ms = tk.StringVar(value="40")

        self.repeat_mode = tk.StringVar(value="until_stopped")
        self.repeat_times = tk.StringVar(value="1")

        self.position_mode = tk.StringVar(value="current")
        self.pos_x = tk.StringVar(value="0")
        self.pos_y = tk.StringVar(value="0")

        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0

        self.translations = load_translations()

        self.setup_style()
        self.build_ui()
        self.start_hotkey_listener()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ------------------------------------------------------------
    # Style
    # ------------------------------------------------------------

    def t(self, key, fallback=None):
        return self.translations.get(key, fallback or key)

    def setup_style(self):
        style = ttk.Style()

        try:
            style.theme_use("vista")
        except Exception:
            pass

        style.configure("TFrame", padding=0)
        style.configure("TLabelframe", padding=8)
        style.configure("TLabelframe.Label", font=("Segoe UI", 10))
        style.configure("TLabel", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("TRadiobutton", font=("Segoe UI", 10))
        style.configure("TCheckbutton", font=("Segoe UI", 10))
        style.configure("Status.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Big.TButton", font=("Segoe UI", 11, "bold"))

    # ------------------------------------------------------------
    # UI
    # ------------------------------------------------------------

    def build_ui(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        self.build_interval_frame(main)
        self.build_middle_area(main)
        self.build_position_frame(main)
        self.build_action_area(main)
        self.build_status(main)
        self.build_support_button(main)

    def build_interval_frame(self, parent):
        frame = ttk.LabelFrame(parent, text=self.t("interval_frame"), padding=12)
        frame.pack(fill="x", pady=(0, 12))

        vcmd = (self.root.register(self.validate_number), "%P")

        labels = [self.t("hours"), self.t("mins"), self.t("secs"), self.t("milliseconds"), self.t("nanoseconds")]
        variables = [
            self.hours_var,
            self.minutes_var,
            self.seconds_var,
            self.milliseconds_var,
            self.nanoseconds_var
        ]

        for col, label in enumerate(labels):
            box = ttk.Frame(frame)
            box.grid(row=0, column=col, sticky="ew", padx=6)

            ttk.Entry(
                box,
                textvariable=variables[col],
                width=12,
                justify="right",
                validate="key",
                validatecommand=vcmd
            ).pack(fill="x")

            ttk.Label(box, text=label, anchor="center").pack(fill="x", pady=(4, 0))

            frame.columnconfigure(col, weight=1)

        random_box = ttk.Frame(frame)
        random_box.grid(row=1, column=0, columnspan=5, sticky="w", pady=(14, 0), padx=6)

        ttk.Checkbutton(
            random_box,
            text=self.t("random_offset"),
            variable=self.random_enabled
        ).pack(side="left")

        ttk.Entry(
            random_box,
            textvariable=self.random_offset_ms,
            width=10,
            justify="right",
            validate="key",
            validatecommand=vcmd
        ).pack(side="left", padx=(16, 6))

        ttk.Label(random_box, text=self.t("milliseconds")).pack(side="left")

    def build_middle_area(self, parent):
        wrapper = ttk.Frame(parent)
        wrapper.pack(fill="x", pady=(0, 12))

        wrapper.columnconfigure(0, weight=1)
        wrapper.columnconfigure(1, weight=1)

        self.build_click_options(wrapper)
        self.build_repeat_options(wrapper)

    def build_click_options(self, parent):
        frame = ttk.LabelFrame(parent, text=self.t("click_options"), padding=12)
        frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text=self.t("mouse_button")).grid(
            row=0,
            column=0,
            sticky="w",
            pady=(0, 12)
        )

        ttk.Combobox(
            frame,
            textvariable=self.mouse_button,
            values=["Left", "Right", "Middle"],
            state="readonly",
            width=20
        ).grid(row=0, column=1, sticky="ew", pady=(0, 12), padx=(12, 0))

        ttk.Label(frame, text=self.t("click_type_label")).grid(
            row=1,
            column=0,
            sticky="w"
        )

        ttk.Combobox(
            frame,
            textvariable=self.click_type,
            values=["Single", "Double"],
            state="readonly",
            width=20
        ).grid(row=1, column=1, sticky="ew", padx=(12, 0))

    def build_repeat_options(self, parent):
        frame = ttk.LabelFrame(parent, text=self.t("click_repeat"), padding=12)
        frame.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        ttk.Radiobutton(
            frame,
            text=self.t("repeat"),
            variable=self.repeat_mode,
            value="repeat"
        ).grid(row=0, column=0, sticky="w", pady=(0, 12))

        ttk.Entry(
            frame,
            textvariable=self.repeat_times,
            width=10,
            justify="right"
        ).grid(row=0, column=1, sticky="w", padx=(20, 8), pady=(0, 12))

        ttk.Label(frame, text=self.t("times")).grid(row=0, column=2, sticky="w", pady=(0, 12))

        ttk.Radiobutton(
            frame,
            text=self.t("repeat_until_stopped"),
            variable=self.repeat_mode,
            value="until_stopped"
        ).grid(row=1, column=0, columnspan=3, sticky="w")

    def build_position_frame(self, parent):
        frame = ttk.LabelFrame(parent, text=self.t("cursor_position"), padding=12)
        frame.pack(fill="x", pady=(0, 14))

        frame.columnconfigure(0, weight=0)
        frame.columnconfigure(1, weight=0)
        frame.columnconfigure(2, weight=0)
        frame.columnconfigure(3, weight=0)
        frame.columnconfigure(4, weight=0)
        frame.columnconfigure(5, weight=0)
        frame.columnconfigure(6, weight=1)

        ttk.Radiobutton(
            frame,
            text=self.t("current_location"),
            variable=self.position_mode,
            value="current"
        ).grid(row=0, column=0, sticky="w", padx=(0, 28))

        ttk.Radiobutton(
            frame,
            text=self.t("fixed_location"),
            variable=self.position_mode,
            value="fixed"
        ).grid(row=0, column=1, sticky="w", padx=(0, 18))

        ttk.Button(
            frame,
            text=self.t("pick_location"),
            command=self.pick_location
        ).grid(row=0, column=2, padx=(0, 18))

        ttk.Label(frame, text="X").grid(row=0, column=3, sticky="e")

        ttk.Entry(
            frame,
            textvariable=self.pos_x,
            width=10,
            justify="right"
        ).grid(row=0, column=4, padx=(6, 18))

        ttk.Label(frame, text="Y").grid(row=0, column=5, sticky="e")

        ttk.Entry(
            frame,
            textvariable=self.pos_y,
            width=10,
            justify="right"
        ).grid(row=0, column=6, sticky="w", padx=(6, 0))

    def build_action_area(self, parent):
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=(0, 10))

        self.f6_button = ttk.Button(
            frame,
            text=self.t("start_stop_button"),
            command=self.toggle_clicking,
            style="Big.TButton"
        )
        self.f6_button.pack(fill="x", ipady=12)


    def build_support_button(self, parent):
        footer = ttk.Frame(parent)
        footer.pack(fill="x", pady=(10, 0))

        btn = tk.Button(
            footer,
            text=self.t("support_button"),
            width=18,
            command=self.show_donate_window,
            bg="#f2f2f2",
            fg="#000000",
            relief="raised",
            bd=1,
            padx=8,
            pady=4
        )
        btn.pack(anchor="e")

    def build_status(self, parent):
        self.status_var = tk.StringVar(value=self.t("status_ready"))

        self.status_label = ttk.Label(
            parent,
            textvariable=self.status_var,
            style="Status.TLabel",
            anchor="center"
        )

        self.status_label.pack(fill="x", pady=(4, 0))

        hint = self.t("status_hint")

        ttk.Label(
            parent,
            text=hint,
            anchor="center",
            foreground="#555555"
        ).pack(fill="x", pady=(6, 0))


    # ------------------------------------------------------------
    # Donate window
    # ------------------------------------------------------------

    def show_donate_window(self):
        win = tk.Toplevel(self.root)
        win.title(self.t("donate_window_title"))
        win.geometry("560x450")
        win.minsize(560, 450)
        win.resizable(False, False)
        win.transient(self.root)
        win.attributes("-topmost", True)

        try:
            win.iconbitmap(ICON_PATH)
        except Exception:
            pass

        wrapper = ttk.Frame(win, padding=18)
        wrapper.pack(fill="both", expand=True)

        title = ttk.Label(
            wrapper,
            text=self.t("donate_title"),
            font=("Segoe UI", 14, "bold")
        )
        title.pack(anchor="w", pady=(0, 10))

        description = self.t("donate_description")

        ttk.Label(
            wrapper,
            text=description,
            wraplength=510,
            justify="left"
        ).pack(anchor="w", pady=(0, 16))

        info = ttk.LabelFrame(wrapper, text=self.t("bank_transfer"), padding=12)
        info.pack(fill="x", pady=(0, 14))

        info.columnconfigure(1, weight=1)

        ttk.Label(info, text=self.t("recipient_label")).grid(row=0, column=0, sticky="w", pady=(0, 8))
        ttk.Label(info, text=DONATE_NAME).grid(row=0, column=1, sticky="w", pady=(0, 8))

        ttk.Label(info, text=self.t("account_label")).grid(row=1, column=0, sticky="w", pady=(0, 8))
        ttk.Label(info, text=DONATE_ACCOUNT).grid(row=1, column=1, sticky="w", pady=(0, 8))

        ttk.Label(info, text=self.t("iban_label")).grid(row=2, column=0, sticky="w")

        iban_entry = ttk.Entry(info, justify="left")
        iban_entry.insert(0, DONATE_IBAN)
        iban_entry.configure(state="readonly")
        iban_entry.grid(row=2, column=1, sticky="ew", padx=(0, 8))

        ttk.Button(
            info,
            text=self.t("copy_iban"),
            command=lambda: self.copy_to_clipboard(DONATE_IBAN, self.t("copied_iban"))
        ).grid(row=2, column=2, sticky="e")

        campaigns = ttk.LabelFrame(wrapper, text=self.t("campaigns"), padding=12)
        campaigns.pack(fill="x", pady=(0, 14))

        ttk.Label(
            campaigns,
            text=self.t("campaign_text"),
            wraplength=500,
            justify="left"
        ).pack(anchor="w", pady=(0, 8))

        campaign_row = ttk.Frame(campaigns)
        campaign_row.pack(fill="x")

        campaign_entry = ttk.Entry(campaign_row)
        campaign_entry.insert(0, DONATE_CAMPAIGNS_URL)
        campaign_entry.configure(state="readonly")
        campaign_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        ttk.Button(
            campaign_row,
            text=self.t("open_button"),
            command=lambda: self.open_url(DONATE_CAMPAIGNS_URL)
        ).pack(side="left")

        buttons = ttk.Frame(wrapper)
        buttons.pack(fill="x", pady=(2, 0))

        ttk.Button(
            buttons,
            text=self.t("copy_email"),
            command=lambda: self.copy_to_clipboard(DONATE_EMAIL, self.t("copied_email"))
        ).pack(side="left")

        ttk.Button(
            buttons,
            text=self.t("close_button"),
            command=win.destroy
        ).pack(side="right")

        win.grab_set()
        win.focus_force()

    def copy_to_clipboard(self, value, status_message=None):
        if status_message is None:
            status_message = self.t("copied_to_clipboard")
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(value)
            self.root.update()
            self.status_var.set(status_message)
        except Exception as e:
            messagebox.showerror(self.t("clipboard_error_title"), str(e))

    def open_url(self, url):
        try:
            webbrowser.open_new_tab(url)
            self.status_var.set(self.t("opened_url", fallback="Opened: {url}").format(url=url))
        except Exception as e:
            messagebox.showerror(self.t("browser_error_title"), str(e))


    # ------------------------------------------------------------
    # Window topmost behavior
    # ------------------------------------------------------------

    def on_window_minimize(self, event=None):
        try:
            if self.root.state() == "iconic":
                self.root.attributes("-topmost", False)
        except Exception:
            pass

    def on_window_restore(self, event=None):
        try:
            if self.root.state() != "iconic":
                self.root.attributes("-topmost", True)
        except Exception:
            pass

    # ------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------

    def validate_number(self, value):
        return value == "" or value.isdigit()

    def safe_int(self, value, default=0):
        try:
            if value.strip() == "":
                return default
            return int(value)
        except Exception:
            return default

    # ------------------------------------------------------------
    # Interval
    # ------------------------------------------------------------

    def get_interval_seconds(self):
        hours = self.safe_int(self.hours_var.get())
        minutes = self.safe_int(self.minutes_var.get())
        seconds = self.safe_int(self.seconds_var.get())
        milliseconds = self.safe_int(self.milliseconds_var.get())
        nanoseconds = self.safe_int(self.nanoseconds_var.get())

        total = 0.0
        total += hours * 3600
        total += minutes * 60
        total += seconds
        total += milliseconds / 1_000
        total += nanoseconds / 1_000_000_000

        if total <= 0:
            total = 0.001

        if self.random_enabled.get():
            offset_ms = self.safe_int(self.random_offset_ms.get())

            if offset_ms > 0:
                offset = random.uniform(
                    -offset_ms / 1000,
                    offset_ms / 1000
                )
                total = max(0.000001, total + offset)

        return total

    # ------------------------------------------------------------
    # Position
    # ------------------------------------------------------------

    def pick_location(self):
        messagebox.showinfo(
            self.t("pick_location"),
            self.t("pick_location_hint")
        )

        self.root.after(3000, self.save_current_position)

    def save_current_position(self):
        x, y = pyautogui.position()

        self.pos_x.set(str(x))
        self.pos_y.set(str(y))
        self.position_mode.set("fixed")
        self.status_var.set(f"Picked location: X {x}, Y {y}")

    def move_if_fixed(self):
        if self.position_mode.get() == "fixed":
            x = self.safe_int(self.pos_x.get())
            y = self.safe_int(self.pos_y.get())
            pyautogui.moveTo(x, y, duration=0)

    # ------------------------------------------------------------
    # Clicking
    # ------------------------------------------------------------

    def get_pyautogui_button(self):
        selected = self.mouse_button.get()

        if selected == "Right":
            return "right"

        if selected == "Middle":
            return "middle"

        return "left"

    def perform_click(self):
        self.move_if_fixed()

        button = self.get_pyautogui_button()

        if self.click_type.get() == "Double":
            pyautogui.click(button=button, clicks=2, interval=0)
        else:
            pyautogui.click(button=button)

    def click_loop(self):
        try:
            if self.repeat_mode.get() == "repeat":
                times = self.safe_int(self.repeat_times.get(), default=1)
                times = max(1, times)

                for _ in range(times):
                    if not self.running:
                        break

                    self.perform_click()
                    self.precise_sleep(self.get_interval_seconds())

                self.root.after(0, self.stop_clicking)

            else:
                while self.running:
                    self.perform_click()
                    self.precise_sleep(self.get_interval_seconds())

        except pyautogui.FailSafeException:
            self.root.after(0, self.emergency_stop)

        except Exception as e:
            self.root.after(0, lambda: self.error_stop(str(e)))

    def precise_sleep(self, seconds):
        if seconds <= 0:
            return

        target = time.perf_counter_ns() + int(seconds * 1_000_000_000)

        while self.running:
            remaining_ns = target - time.perf_counter_ns()

            if remaining_ns <= 0:
                break

            if remaining_ns > 2_000_000:
                time.sleep((remaining_ns - 1_000_000) / 1_000_000_000)
            else:
                pass

    # ------------------------------------------------------------
    # Start / Stop
    # ------------------------------------------------------------

    def toggle_clicking(self):
        if self.running:
            self.stop_clicking()
        else:
            self.start_clicking()

    def start_clicking(self):
        if self.running:
            return

        self.running = True
        self.f6_button.config(text=self.t("running_button"))
        self.status_var.set(self.t("status_running"))

        self.click_thread = threading.Thread(
            target=self.click_loop,
            daemon=True
        )

        self.click_thread.start()

    def stop_clicking(self):
        if not self.running:
            return

        self.running = False
        self.f6_button.config(text=self.t("start_stop_button"))
        self.status_var.set(self.t("status_stopped"))

    def emergency_stop(self):
        self.running = False
        self.f6_button.config(text=self.t("start_stop_button"))
        self.status_var.set(self.t("status_emergency"))

    def error_stop(self, message):
        self.running = False
        self.f6_button.config(text=self.t("start_stop_button"))
        self.status_var.set(self.t("status_error"))
        messagebox.showerror(self.t("error_title"), message)

    # ------------------------------------------------------------
    # Global F6 hotkey
    # ------------------------------------------------------------

    def start_hotkey_listener(self):
        def on_press(key):
            try:
                if key == keyboard.Key.f6:
                    self.root.after(0, self.toggle_clicking)
            except Exception:
                pass

        self.listener = keyboard.Listener(on_press=on_press)
        self.listener.daemon = True
        self.listener.start()

    # ------------------------------------------------------------
    # Close
    # ------------------------------------------------------------

    def on_close(self):
        self.running = False

        if self.listener:
            try:
                self.listener.stop()
            except Exception:
                pass

        self.root.destroy()


def main():
    root = tk.Tk()
    NanoAutoClicker(root)
    root.mainloop()


if __name__ == "__main__":
    main()