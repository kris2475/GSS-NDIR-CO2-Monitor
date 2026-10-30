from datetime import datetime
import queue
import re
import threading
from tkinter import (
    END,
    BooleanVar,
    Button,
    Entry,
    Frame,
    Label,
    LabelFrame,
    StringVar,
    Tk,
    filedialog,
    messagebox,
    ttk,
)
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import serial
import serial.tools.list_ports


class CO2MonitorApp:

  def __init__(self, root):
    self.root = root
    self.root.title("GSS CO2 Sensor Monitor & Logger")
    self.root.geometry("950x750")

    self.ser = None
    self.is_connected = False
    self.is_logging = False
    self.log_file = None
    self.data_queue = queue.Queue()

    # Time tracking for t=0 and rolling window
    self.start_time = None
    self.elapsed_data = []
    self.filtered_data = []
    self.raw_data = []
    self.window_seconds = 60  # Rolling 60 seconds window

    self.create_widgets()
    self.refresh_ports()

    # Start checking the queue for incoming serial data
    self.root.after(100, self.process_queue)

  def create_widgets(self):
    # --- Top Control Panel ---
    control_frame = LabelFrame(
        self.root, text="Connection & Controls", padx=10, pady=10
    )
    control_frame.pack(fill="x", padx=10, pady=10)

    Label(control_frame, text="Port:").grid(row=0, column=0, sticky="w")
    self.port_combo = ttk.Combobox(control_frame, width=12, state="readonly")
    self.port_combo.grid(row=0, column=1, padx=5)

    Button(control_frame, text="Refresh", command=self.refresh_ports).grid(
        row=0, column=2, padx=5
    )

    Label(control_frame, text="Baud:").grid(row=0, column=3, padx=5)
    self.baud_entry = Entry(control_frame, width=8)
    self.baud_entry.insert(0, "115200")
    self.baud_entry.grid(row=0, column=4, padx=5)

    self.connect_btn = Button(
        control_frame,
        text="Connect",
        command=self.toggle_connection,
        bg="green",
        fg="white",
    )
    self.connect_btn.grid(row=0, column=5, padx=10)

    self.reset_time_btn = Button(
        control_frame,
        text="Reset t=0",
        command=self.reset_timer,
        state="disabled",
    )
    self.reset_time_btn.grid(row=0, column=6, padx=5)

    self.log_btn = Button(
        control_frame,
        text="Start Logging to CSV",
        command=self.toggle_logging,
        state="disabled",
    )
    self.log_btn.grid(row=0, column=7, padx=10)

    # Status Label
    self.status_lbl = Label(
        control_frame, text="Status: Disconnected", fg="red"
    )
    self.status_lbl.grid(row=1, column=0, columnspan=4, sticky="w", pady=5)

    # --- Middle: Live Plotting Panel ---
    plot_frame = Frame(self.root)
    plot_frame.pack(fill="both", expand=True, padx=10, pady=5)

    self.fig = Figure(figsize=(8, 4.5), dpi=100)
    self.ax = self.fig.add_subplot(111)
    self.ax.set_title("Real-Time CO2 Sensor Stream (Rolling 60s)")
    self.ax.set_xlabel("Elapsed Time (Seconds)")
    self.ax.set_ylabel("PPM")

    (self.line_filtered,) = self.ax.plot(
        [], [], label="Filtered (Z)", color="blue", linewidth=2
    )
    (self.line_raw,) = self.ax.plot(
        [], [], label="Raw (z)", color="orange", linestyle="--"
    )
    self.ax.legend(loc="upper left")
    self.fig.tight_layout()

    self.canvas = FigureCanvasTkAgg(self.fig, master=plot_frame)
    self.canvas.get_tk_widget().pack(fill="both", expand=True)

  def refresh_ports(self):
    ports = [port.device for port in serial.tools.list_ports.comports()]
    self.port_combo["values"] = ports
    if ports:
      self.port_combo.current(0)

  def reset_timer(self):
    self.start_time = datetime.now()
    self.elapsed_data.clear()
    self.filtered_data.clear()
    self.raw_data.clear()

  def toggle_connection(self):
    if not self.is_connected:
      port = self.port_combo.get()
      baud = self.baud_entry.get()
      if not port:
        messagebox.showerror("Error", "Please select a valid COM port.")
        return
      try:
        self.ser = serial.Serial(port, int(baud), timeout=1)
        self.is_connected = True
        self.connect_btn.config(text="Disconnect", bg="red")
        self.log_btn.config(state="normal")
        self.reset_time_btn.config(state="normal")
        self.status_lbl.config(
            text=f"Status: Connected to {port} @ {baud}", fg="green"
        )

        # Initialize t=0 anchor
        self.reset_timer()

        # Start background reading thread
        self.thread = threading.Thread(target=self.read_serial, daemon=True)
        self.thread.start()
      except Exception as e:
        messagebox.showerror("Connection Error", str(e))
    else:
      self.disconnect()

  def disconnect(self):
    if self.is_logging:
      self.toggle_logging()
    self.is_connected = False
    if self.ser and self.ser.is_open:
      self.ser.close()
    self.connect_btn.config(text="Connect", bg="green")
    self.log_btn.config(state="disabled")
    self.reset_time_btn.config(state="disabled")
    self.status_lbl.config(text="Status: Disconnected", fg="red")

  def toggle_logging(self):
    if not self.is_logging:
      filename = filedialog.asksaveasfilename(
          defaultextension=".csv",
          filetypes=[("CSV Files", "*.csv")],
          title="Save CO2 Data As",
      )
      if filename:
        try:
          self.log_file = open(filename, "w", newline="")
          self.log_file.write(
              "Timestamp,Elapsed_Seconds,Filtered_CO2_PPM,Raw_CO2_PPM\n"
          )
          self.is_logging = True
          self.log_btn.config(text="Stop Logging", bg="orange")
        except Exception as e:
          messagebox.showerror("File Error", f"Could not open file: {e}")
    else:
      self.is_logging = False
      if self.log_file:
        self.log_file.close()
      self.log_btn.config(text="Start Logging to CSV", bg="SystemButtonFace")

  def read_serial(self):
    while self.is_connected:
      try:
        if self.ser.in_waiting > 0:
          line = self.ser.readline().decode("utf-8", errors="ignore").strip()
          if line:
            self.data_queue.put(line)
      except Exception:
        break

  def process_queue(self):
    while not self.data_queue.empty():
      line = self.data_queue.get()
      match_z = re.search(r"Z\s+(\d+)", line)
      match_zz = re.search(r"z\s+(\d+)", line)

      if match_z:
        filtered_co2 = int(match_z.group(1))
        raw_co2 = int(match_zz.group(1)) if match_zz else 0
        now = datetime.now()

        if self.start_time is None:
          self.start_time = now

        elapsed = (now - self.start_time).total_seconds()

        # Update Data Lists
        self.elapsed_data.append(elapsed)
        self.filtered_data.append(filtered_co2)
        self.raw_data.append(raw_co2)

        # Rolling 60-second window filter
        while self.elapsed_data and (
            self.elapsed_data[-1] - self.elapsed_data[0] > self.window_seconds
        ):
          self.elapsed_data.pop(0)
          self.filtered_data.pop(0)
          self.raw_data.pop(0)

        # Update Plot Limits
        if self.elapsed_data:
          latest_t = self.elapsed_data[-1]
          start_t = max(0, latest_t - self.window_seconds)
          self.ax.set_xlim(
              start_t, max(start_t + self.window_seconds, latest_t + 1)
          )

        # Dynamically scale Y axis based on current window readings
        all_vals = self.filtered_data + self.raw_data
        if all_vals:
          self.ax.set_ylim(
              max(0, min(all_vals) - 200), max(all_vals) + 200
          )

        self.line_filtered.set_xdata(self.elapsed_data)
        self.line_filtered.set_ydata(self.filtered_data)
        self.line_raw.set_xdata(self.elapsed_data)
        self.line_raw.set_ydata(self.raw_data)

        self.canvas.draw()

        # Write to CSV if logging is active
        if self.is_logging and self.log_file:
          self.log_file.write(
              f"{now},{elapsed:.2f},{filtered_co2},{raw_co2}\n"
          )
          self.log_file.flush()

    self.root.after(100, self.process_queue)


if __name__ == "__main__":
  root = Tk()
  app = CO2MonitorApp(root)
  root.mainloop()