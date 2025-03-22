import tkinter as tk
from tkinter import ttk
import psutil
import time
import threading
import datetime
import csv
import os
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import numpy as np
from collections import deque

class CPUMonitorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Monitor de CPU con Gráficas")
        self.root.geometry("950x700")
        self.root.minsize(800, 600)
        
        # Variables para almacenar datos
        self.cpu_percent = 0
        self.per_cpu_percent = []
        self.num_threads = psutil.cpu_count(logical=True)
        
        # Variables para el historial y gráficas
        self.history_length = 60  # 1 minuto de historial en gráfica
        self.timestamps = deque(maxlen=self.history_length)
        self.cpu_history = deque(maxlen=self.history_length)
        self.per_cpu_history = [deque(maxlen=self.history_length) for _ in range(self.num_threads)]
        
        # Variables para el registro
        self.is_logging = False
        self.log_file = None
        self.csv_writer = None
        self.log_filename = ""
        
        # Crear la interfaz
        self.create_widgets()
        
        # Iniciar thread de monitoreo en segundo plano
        self.running = True
        self.monitor_thread = threading.Thread(target=self.monitor_cpu)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        
        # Iniciar actualizaciones
        self.update_display()
        self.update_plots()
        
        # Manejar cierre de ventana
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
    
    def create_widgets(self):
        # Panel principal con pestañas
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Pestaña de monitor
        self.monitor_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.monitor_frame, text="Monitor")
        
        # Pestaña de gráficas
        self.graphs_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.graphs_frame, text="Gráficas")
        
        # Configurar pestaña de monitor
        self.setup_monitor_tab()
        
        # Configurar pestaña de gráficas
        self.setup_graphs_tab()
    
    def setup_monitor_tab(self):
        # Frame principal para la pestaña de monitor
        main_frame = tk.Frame(self.monitor_frame, bg="#2c3e50")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Frame para el encabezado (título, porcentaje y botones)
        header_frame = tk.Frame(main_frame, bg="#2c3e50")
        header_frame.pack(fill=tk.X, padx=10, pady=(10, 0))  # Sin espacio inferior
        
        # Título "Monitor de CPU"
        self.title_label = tk.Label(
            header_frame,
            text="Monitor de CPU",
            font=("Arial", 16, "bold"),
            fg="white",
            bg="#2c3e50"
        )
        self.title_label.pack(side=tk.LEFT, padx=10, pady=0)
        
        # Etiqueta para mostrar el porcentaje total
        self.percentage_label = tk.Label(
            header_frame,
            text="0%",
            font=("Arial", 36, "bold"),
            fg="#27ae60",
            bg="#2c3e50"
        )
        self.percentage_label.pack(side=tk.LEFT, padx=10, pady=0)
        
        # Frame para los botones y la etiqueta de estado
        button_frame = tk.Frame(header_frame, bg="#2c3e50")
        button_frame.pack(side=tk.RIGHT, padx=10, pady=0)
        
        # Botones para controlar el registro
        self.start_button = tk.Button(
            button_frame,
            text="Iniciar Registro",
            command=self.start_logging,
            bg="#27ae60",
            fg="white",
            padx=10
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = tk.Button(
            button_frame,
            text="Detener Registro",
            command=self.stop_logging,
            bg="#e74c3c",
            fg="white",
            padx=10,
            state=tk.DISABLED
        )
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        # Etiqueta para el estado del registro
        self.log_label = tk.Label(
            button_frame,
            text="Listo para registrar datos",
            padx=10,
            bg="#2c3e50",
            fg="white"
        )
        self.log_label.pack(side=tk.LEFT, padx=10)
        
        # Frame para mostrar información actual (gráfica y uso por thread)
        info_frame = tk.Frame(main_frame, bg="#2c3e50")
        info_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))  # Sin espacio superior
        
        # Canvas para mostrar gráfica de uso total
        self.fig_total, self.ax_total = plt.subplots(figsize=(8, 2), dpi=100)  # Ajustado el alto
        self.ax_total.set_ylim(0, 100)
        self.ax_total.set_title('Uso de CPU Total (Tiempo Real)')
        self.ax_total.set_ylabel('Uso (%)')
        self.ax_total.grid(True, linestyle='--', alpha=0.7)
        self.line_total, = self.ax_total.plot([], [], 'b-', linewidth=2)
        self.fig_total.tight_layout()
        
        self.canvas_total = FigureCanvasTkAgg(self.fig_total, master=info_frame)
        self.canvas_total.draw()
        self.canvas_total.get_tk_widget().pack(fill=tk.BOTH, expand=True, pady=(0, 10))  # Sin espacio superior
        
        # Frame para mostrar uso por thread
        self.cores_frame = tk.Frame(info_frame, bg="#2c3e50")
        self.cores_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))  # Sin espacio superior
        
        # Etiqueta para mostrar threads
        thread_label = tk.Label(
            self.cores_frame,
            text="Uso por Thread:",
            font=("Arial", 12, "bold"),
            fg="white",
            bg="#2c3e50"
        )
        thread_label.grid(row=0, column=0, columnspan=4, sticky='w', pady=5)
        
        # Crear medidores para cada thread
        self.thread_bars = []
        self.thread_labels = []
        
        # Distribuir en una cuadrícula de 4 columnas
        cols = 4
        for i in range(self.num_threads):
            row = (i // cols) + 1
            col = i % cols
            
            # Frame para cada thread
            thread_frame = tk.Frame(self.cores_frame, bg="#2c3e50")
            thread_frame.grid(row=row, column=col, padx=5, pady=5, sticky='w')
            
            # Etiqueta para el número de thread
            thread_num = tk.Label(
                thread_frame,
                text=f"Thread {i}:",
                fg="white",
                bg="#2c3e50",
                width=8,
                anchor='w'
            )
            thread_num.grid(row=0, column=0, sticky='w')
            
            # Barra de progreso
            bar = ttk.Progressbar(
                thread_frame,
                orient='horizontal',
                length=100,
                mode='determinate'
            )
            bar.grid(row=0, column=1, padx=2)
            
            # Etiqueta para el valor
            value_label = tk.Label(
                thread_frame,
                text="0%",
                fg="white",
                bg="#2c3e50",
                width=5
            )
            value_label.grid(row=0, column=2, padx=2)
            
            self.thread_bars.append(bar)
            self.thread_labels.append(value_label)
    
    def setup_graphs_tab(self):
        # Crear figura para los gráficos
        self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(9, 8), dpi=100)
        
        # Configurar gráfico superior (CPU total)
        self.ax1.set_ylim(0, 100)
        self.ax1.set_title('Uso Total de CPU')
        self.ax1.set_ylabel('Uso (%)')
        self.ax1.grid(True, linestyle='--', alpha=0.7)
        self.line1, = self.ax1.plot([], [], 'b-', linewidth=1.5)
        
        # Configurar gráfico inferior (CPU por thread)
        self.ax2.set_ylim(0, 100)
        self.ax2.set_title('Uso por Thread')
        self.ax2.set_ylabel('Uso (%)')
        self.ax2.grid(True, linestyle='--', alpha=0.7)
        
        # Crear una línea para cada thread
        self.lines = []
        for i in range(self.num_threads):
            line, = self.ax2.plot([], [], label=f'Thread {i}', linewidth=1, alpha=0.8)
            self.lines.append(line)
        
        # Añadir leyenda
        self.ax2.legend(loc='upper center', bbox_to_anchor=(0.5, -0.15), 
                       fancybox=True, shadow=True, ncol=6)
        
        # Ajustar espaciado
        self.fig.tight_layout()
        
        # Crear canvas para mostrar la figura
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graphs_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def start_logging(self):
        """Inicia el registro de datos en un archivo CSV"""
        if self.is_logging:
            return
            
        # Crear directorio de logs si no existe
        log_dir = "cpu_logs"
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        # Crear nombre de archivo con timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_filename = f"{log_dir}/cpu_log_{timestamp}.csv"
        
        # Crear encabezados para el CSV
        headers = ["Timestamp", "CPU_Total"]
        for i in range(self.num_threads):
            headers.append(f"Thread_{i}")
            
        # Abrir archivo y escribir encabezados
        self.log_file = open(self.log_filename, 'w', newline='')
        self.csv_writer = csv.writer(self.log_file)
        self.csv_writer.writerow(headers)
        
        # Actualizar estado
        self.is_logging = True
        self.log_label.config(text=f"Registrando en: {os.path.basename(self.log_filename)}")
        
        # Actualizar botones
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
    
    def stop_logging(self):
        """Detiene el registro de datos"""
        if not self.is_logging:
            return
            
        # Cerrar archivo
        if self.log_file:
            self.log_file.close()
            self.log_file = None
            self.csv_writer = None
            
        # Actualizar estado
        self.is_logging = False
        self.log_label.config(text=f"Registro detenido. Último archivo: {os.path.basename(self.log_filename)}")
        
        # Actualizar botones
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
    
    def log_data(self):
        """Guarda los datos actuales en el archivo CSV"""
        if not self.is_logging or not self.csv_writer:
            return
            
        # Obtener timestamp actual
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        # Preparar fila de datos
        row_data = [timestamp, self.cpu_percent]
        row_data.extend(self.per_cpu_percent)
        
        # Escribir al CSV
        self.csv_writer.writerow(row_data)
        self.log_file.flush()  # Asegurar que se escriba al disco
    
    def monitor_cpu(self):
        """Monitorea el CPU en segundo plano para lecturas más precisas"""
        while self.running:
            # Obtener timestamp actual
            now = datetime.datetime.now()
            
            # Obtener porcentaje de uso total
            self.cpu_percent = psutil.cpu_percent(interval=0.5, percpu=False)
            
            # Obtener porcentaje por thread
            self.per_cpu_percent = psutil.cpu_percent(interval=0.1, percpu=True)
            
            # Actualizar historial para gráficas
            self.timestamps.append(now)
            self.cpu_history.append(self.cpu_percent)
            
            for i, cpu_val in enumerate(self.per_cpu_percent):
                if i < len(self.per_cpu_history):
                    self.per_cpu_history[i].append(cpu_val)
            
            # Registrar datos si está activo
            self.log_data()
            
            # Pequeña pausa
            time.sleep(0.4)  # Ajustado para un intervalo total de ~1 segundo
    
    def update_display(self):
        """Actualiza la interfaz de usuario con los valores actuales"""
        if not self.running:
            return
        
        # Actualizar el texto de la etiqueta principal
        self.percentage_label.config(text=f"{self.cpu_percent:.1f}%")
        
        # Cambiar el color según el uso
        if self.cpu_percent < 50:
            self.percentage_label.config(fg="#27ae60")  # Verde para uso bajo
        elif self.cpu_percent < 80:
            self.percentage_label.config(fg="#f39c12")  # Naranja para uso medio
        else:
            self.percentage_label.config(fg="#e74c3c")  # Rojo para uso alto
        
        # Actualizar barras de progreso de threads
        for i, (bar, label) in enumerate(zip(self.thread_bars, self.thread_labels)):
            if i < len(self.per_cpu_percent):
                value = self.per_cpu_percent[i]
                bar['value'] = value
                label.config(text=f"{value:.0f}%")
                
                # Cambiar color de texto según valor
                if value < 50:
                    label.config(fg="#27ae60")  # Verde
                elif value < 80:
                    label.config(fg="#f39c12")  # Naranja
                else:
                    label.config(fg="#e74c3c")  # Rojo
        
        # Programar la próxima actualización
        self.update_id = self.root.after(500, self.update_display)
    
    def update_plots(self):
        """Actualiza las gráficas con los datos acumulados"""
        if not self.running:
            return
        
        try:
            # Convertir deques a listas para plotting
            times = list(self.timestamps)
            cpu_values = list(self.cpu_history)
            
            if len(times) > 1:
                # Actualizar gráfica de CPU total en pestaña Monitor
                x_total = range(len(cpu_values))
                self.line_total.set_data(x_total, cpu_values)
                self.ax_total.set_xlim(0, max(len(cpu_values) - 1, 10))
                self.ax_total.set_xticks([])  # Ocultar ticks en X
                self.canvas_total.draw_idle()
                
                # Actualizar gráfica de CPU total en pestaña Gráficas
                self.line1.set_data(times, cpu_values)
                self.ax1.set_xlim(min(times), max(times))
                self.ax1.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: (min(times) + datetime.timedelta(seconds=x/10)).strftime('%H:%M:%S')))
                
                # Actualizar líneas por thread
                for i, line in enumerate(self.lines):
                    if i < len(self.per_cpu_history):
                        per_cpu_values = list(self.per_cpu_history[i])
                        line.set_data(times, per_cpu_values)
                
                # Actualizar límites y ejes
                self.ax2.set_xlim(min(times), max(times))
                self.ax2.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, pos: (min(times) + datetime.timedelta(seconds=x/10)).strftime('%H:%M:%S')))
                
                # Redibujar figura completa
                self.fig.canvas.draw_idle()
        
        except Exception as e:
            print(f"Error al actualizar gráficas: {e}")
        
        # Programar próxima actualización
        self.plot_id = self.root.after(1000, self.update_plots)
    
    def on_closing(self):
        """Limpia los recursos al cerrar"""
        # Detener registro si está activo
        if self.is_logging:
            self.stop_logging()
            
        # Detener monitoreo
        self.running = False
        time.sleep(0.5)  # Dar tiempo al thread para terminar
        
        # Cancelar actualizaciones pendientes
        if hasattr(self, 'update_id'):
            self.root.after_cancel(self.update_id)
        if hasattr(self, 'plot_id'):
            self.root.after_cancel(self.plot_id)
        
        # Cerrar ventana
        plt.close('all')  # Cerrar todas las figuras de matplotlib
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = CPUMonitorApp(root)
    root.mainloop()