import argparse
import queue
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

import tango_music_score_v2 as engine


IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform.startswith("win")
FONT_UI = "Segoe UI" if IS_WIN else ("Helvetica Neue" if IS_MAC else "DejaVu Sans")
FONT_MONO = "Consolas" if IS_WIN else ("Menlo" if IS_MAC else "DejaVu Sans Mono")


def resource_path(name):
    """Locate bundled resource both in development and inside a PyInstaller EXE."""
    base = getattr(sys, "_MEIPASS", None) or str(Path(__file__).resolve().parent)
    return str(Path(base) / name)


class TangoScoreApp:
    def __init__(self, root):
        self.root = root
        root.title("Tango Music Score Generator v2")
        root.geometry("860x680" if IS_MAC else "760x620")
        root.minsize(800 if IS_MAC else 700, 600 if IS_MAC else 560)

        self.input_dir = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.level = tk.IntVar(value=2)
        self.mode = tk.StringVar(value="musical")
        self.all_levels = tk.BooleanVar(value=True)
        self.all_modes = tk.BooleanVar(value=False)
        self.recursive = tk.BooleanVar(value=False)
        self.csv = tk.BooleanVar(value=False)
        self.keys = tk.IntVar(value=2)
        self.beats = tk.IntVar(value=4)
        self.subdivision = tk.IntVar(value=4)
        self.offset = tk.IntVar(value=0)
        self.downbeat = tk.StringVar(value="")
        self.pack_name = tk.StringVar(value="Tango")
        self.running = False
        self.q = queue.Queue()

        self._set_window_icon()
        self._build_ui()
        self.root.after(100, self._poll_log)

    def _set_window_icon(self):
        try:
            if not IS_WIN:
                raise RuntimeError("iconbitmap(.ico) is Windows-only")
            self.root.iconbitmap(resource_path("maximo_icon.ico"))
        except Exception:
            try:
                self._icon_img = tk.PhotoImage(file=resource_path("maximo_logo.png"))
                self.root.iconphoto(True, self._icon_img)
            except Exception:
                pass

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        header = ttk.Frame(main)
        header.pack(fill="x", pady=(0, 10))
        try:
            self.logo_img = tk.PhotoImage(file=resource_path("maximo_logo.png"))
            # keep a reference on self, otherwise Tk garbage-collects the image
            self.logo_img = self.logo_img.subsample(2, 2)  # 300px -> 150px wide
            ttk.Label(header, image=self.logo_img).pack(side="left", padx=(0, 16))
        except Exception:
            pass
        text_box = ttk.Frame(header)
        text_box.pack(side="left", fill="x", expand=True)
        title = ttk.Label(text_box, text="Tango Music Score Generator v2", font=(FONT_UI, 18, "bold"))
        title.pack(anchor="w")
        ttk.Label(text_box, text="음원 폴더 → 음악 분석 → JSON / CSV / OSZ 일괄 생성").pack(anchor="w", pady=(6, 0))

        io = ttk.LabelFrame(main, text="입출력", padding=8)
        io.pack(fill="x")
        self._path_row(io, "음원 폴더", self.input_dir, self._choose_input, pad)
        self._path_row(io, "출력 폴더", self.output_dir, self._choose_output, pad)

        opt = ttk.LabelFrame(main, text="채보 설정", padding=8)
        opt.pack(fill="x", pady=10)

        r1 = ttk.Frame(opt); r1.pack(fill="x")
        ttk.Label(r1, text="기본 Level").pack(side="left")
        ttk.Combobox(r1, textvariable=self.level, values=[1,2,3], state="readonly", width=6).pack(side="left", padx=(8,20))
        ttk.Label(r1, text="키 수").pack(side="left")
        ttk.Combobox(r1, textvariable=self.keys, values=[2,4], state="readonly", width=4).pack(side="left", padx=(8,20))
        ttk.Label(r1, text="Mode").pack(side="left")
        ttk.Combobox(r1, textvariable=self.mode, values=["musical","tango","beat","salient","instrument"], state="readonly", width=14).pack(side="left", padx=8)

        r2 = ttk.Frame(opt); r2.pack(fill="x", pady=7)
        ttk.Checkbutton(r2, text="Lv1/Lv2/Lv3 모두 생성", variable=self.all_levels).pack(side="left")
        ttk.Checkbutton(r2, text="모든 Mode 생성", variable=self.all_modes).pack(side="left", padx=18)
        ttk.Checkbutton(r2, text="하위 폴더 포함", variable=self.recursive).pack(side="left")
        ttk.Checkbutton(r2, text="Events CSV 생성", variable=self.csv).pack(side="left", padx=18)

        r3 = ttk.Frame(opt); r3.pack(fill="x", pady=2)
        ttk.Label(r3, text="박자").pack(side="left")
        ttk.Combobox(r3, textvariable=self.beats, values=[2,3,4], state="readonly", width=5).pack(side="left", padx=(6,18))
        ttk.Label(r3, text="Subdivision").pack(side="left")
        ttk.Combobox(r3, textvariable=self.subdivision, values=[2,4,8], state="readonly", width=5).pack(side="left", padx=(6,18))
        ttk.Label(r3, text="Offset(ms)").pack(side="left")
        ttk.Entry(r3, textvariable=self.offset, width=8).pack(side="left", padx=6)
        ttk.Label(r3, text="Downbeat").pack(side="left", padx=(15,4))
        ttk.Entry(r3, textvariable=self.downbeat, width=6).pack(side="left")

        r4 = ttk.Frame(opt); r4.pack(fill="x", pady=(7,0))
        ttk.Label(r4, text="Pack 이름").pack(side="left")
        ttk.Entry(r4, textvariable=self.pack_name, width=20).pack(side="left", padx=8)

        action = ttk.Frame(main)
        action.pack(fill="x", pady=8)
        self.start_btn = ttk.Button(action, text="▶ 음원 일괄 분석 및 OSZ 생성", command=self.start)
        self.start_btn.pack(side="left")
        self.progress = ttk.Progressbar(action, mode="indeterminate")
        self.progress.pack(side="left", fill="x", expand=True, padx=12)

        log_frame = ttk.LabelFrame(main, text="처리 로그", padding=6)
        log_frame.pack(fill="both", expand=True)
        self.log = tk.Text(log_frame, height=18, wrap="word", state="disabled", font=(FONT_MONO, 10 if IS_MAC else 9))
        self.log.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        sb.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=sb.set)

    def _path_row(self, parent, label, var, command, pad):
        row = ttk.Frame(parent); row.pack(fill="x", **pad)
        ttk.Label(row, text=label, width=10).pack(side="left")
        ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(row, text="찾아보기", command=command).pack(side="right")

    def _choose_input(self):
        p = filedialog.askdirectory(title="음원이 들어있는 폴더 선택")
        if p:
            self.input_dir.set(p)
            if not self.output_dir.get():
                self.output_dir.set(str(Path(p) / "charts"))

    def _choose_output(self):
        p = filedialog.askdirectory(title="출력 폴더 선택")
        if p:
            self.output_dir.set(p)

    def _write(self, s):
        self.q.put(str(s))

    def _poll_log(self):
        try:
            while True:
                s = self.q.get_nowait()
                self.log.configure(state="normal")
                self.log.insert("end", s + ("" if s.endswith("\n") else "\n"))
                self.log.see("end")
                self.log.configure(state="disabled")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log)

    def start(self):
        if self.running:
            return
        inp = self.input_dir.get().strip()
        if not inp or not Path(inp).is_dir():
            messagebox.showwarning("입력 폴더", "먼저 음원이 들어있는 폴더를 선택하세요.")
            return
        out = self.output_dir.get().strip() or str(Path(inp) / "charts")
        self.output_dir.set(out)
        Path(out).mkdir(parents=True, exist_ok=True)

        downbeat = None
        if self.downbeat.get().strip():
            try:
                downbeat = int(self.downbeat.get().strip())
            except ValueError:
                messagebox.showwarning("Downbeat", "Downbeat는 숫자로 입력하세요.")
                return

        args = argparse.Namespace(
            input=inp,
            out=out,
            level=int(self.level.get()),
            keys=int(self.keys.get()),
            mode=self.mode.get(),
            all_levels=bool(self.all_levels.get()),
            all_modes=bool(self.all_modes.get()),
            recursive=bool(self.recursive.get()),
            beats=int(self.beats.get()),
            subdivision=int(self.subdivision.get()),
            downbeat=downbeat,
            offset=int(self.offset.get()),
            pack=self.pack_name.get().strip() or "Tango",
            csv=bool(self.csv.get()),
        )

        self.running = True
        self.start_btn.configure(state="disabled")
        self.progress.start(12)
        self._write("=" * 62)
        self._write("TANGO MUSIC SCORE GENERATOR v2 시작")
        self._write(f"입력: {inp}")
        self._write(f"출력: {out}")
        self._write(f"키 수: {int(self.keys.get())}키")
        self._write("=" * 62)

        threading.Thread(target=self._run, args=(args,), daemon=True).start()

    def _run(self, args):
        import contextlib
        import io
        try:
            buf = io.StringIO()
            class Tee:
                def write(self, x):
                    if x:
                        for line in x.rstrip("\n").splitlines() or [""]:
                            self_outer._write(line)
                    return len(x)
                def flush(self):
                    pass
            self_outer = self
            tee = Tee()
            with contextlib.redirect_stdout(tee), contextlib.redirect_stderr(tee):
                engine.batch_process(Path(args.input), args)
            self._write("\n✓ 전체 작업이 완료되었습니다.")
            self.root.after(0, lambda: messagebox.showinfo("완료", f"작업이 완료되었습니다.\n\n출력 폴더:\n{args.out}"))
        except Exception as exc:
            self._write(f"\n✗ 오류: {exc}")
            self.root.after(0, lambda: messagebox.showerror("오류", str(exc)))
        finally:
            self.running = False
            self.root.after(0, self._finish)

    def _finish(self):
        self.progress.stop()
        self.start_btn.configure(state="normal")


def main():
    root = tk.Tk()
    try:
        root.iconname("Tango Music Score Generator")
    except Exception:
        pass
    TangoScoreApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
