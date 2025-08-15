#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Scanner Avancé d'Entrées Vidéo avec Aperçu Temps Réel
Détecte et analyse toutes les sources vidéo disponibles sur le PC
"""

import cv2
import numpy as np
import threading
import time
import platform
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import tkinter as tk
from tkinter import ttk, scrolledtext
from PIL import Image, ImageTk
import queue
import os
import sys

# Installation des dépendances
# pip install opencv-python pillow numpy

# Import optionnel pour plus d'infos Windows
try:
    import win32com.client
    import wmi
    WINDOWS_EXTRAS = True
except ImportError:
    WINDOWS_EXTRAS = False
    print("Note: Installez pywin32 et wmi pour plus d'infos sous Windows")

class VideoSource:
    """Classe représentant une source vidéo"""
    
    def __init__(self, index: int):
        self.index = index
        self.name = f"Camera {index}"
        self.is_available = False
        self.properties = {}
        self.supported_resolutions = []
        self.supported_framerates = []
        self.current_resolution = None
        self.current_fps = 0
        self.backend = None
        self.last_frame = None
        self.error_message = None
        
    def to_dict(self) -> Dict:
        """Convertit les infos en dictionnaire"""
        return {
            "index": self.index,
            "name": self.name,
            "available": self.is_available,
            "backend": self.backend,
            "resolution": self.current_resolution,
            "fps": self.current_fps,
            "properties": self.properties,
            "supported_resolutions": self.supported_resolutions,
            "error": self.error_message
        }

class VideoScanner:
    """Scanner principal pour détecter les sources vidéo"""
    
    # Backends OpenCV à tester
    BACKENDS = {
        "DirectShow": cv2.CAP_DSHOW,
        "V4L2": cv2.CAP_V4L2,
        "MSMF": cv2.CAP_MSMF,
        "AVFoundation": cv2.CAP_AVFOUNDATION,
        "GStreamer": cv2.CAP_GSTREAMER,
        "Default": cv2.CAP_ANY
    }
    
    # Propriétés OpenCV importantes
    PROPERTIES = {
        "Width": cv2.CAP_PROP_FRAME_WIDTH,
        "Height": cv2.CAP_PROP_FRAME_HEIGHT,
        "FPS": cv2.CAP_PROP_FPS,
        "Brightness": cv2.CAP_PROP_BRIGHTNESS,
        "Contrast": cv2.CAP_PROP_CONTRAST,
        "Saturation": cv2.CAP_PROP_SATURATION,
        "Hue": cv2.CAP_PROP_HUE,
        "Gain": cv2.CAP_PROP_GAIN,
        "Exposure": cv2.CAP_PROP_EXPOSURE,
        "White Balance": cv2.CAP_PROP_WB_TEMPERATURE,
        "Focus": cv2.CAP_PROP_FOCUS,
        "Zoom": cv2.CAP_PROP_ZOOM,
        "Format": cv2.CAP_PROP_FORMAT,
        "Mode": cv2.CAP_PROP_MODE,
        "Buffer Size": cv2.CAP_PROP_BUFFERSIZE,
        "Codec": cv2.CAP_PROP_FOURCC
    }
    
    # Résolutions communes à tester
    COMMON_RESOLUTIONS = [
        (320, 240),    # QVGA
        (640, 480),    # VGA
        (800, 600),    # SVGA
        (1024, 768),   # XGA
        (1280, 720),   # HD 720p
        (1280, 960),   # SXGA
        (1920, 1080),  # Full HD 1080p
        (2560, 1440),  # QHD
        (3840, 2160),  # 4K UHD
    ]
    
    def __init__(self):
        self.sources = []
        self.scanning = False
        self.os_type = platform.system()
        
    def detect_backend(self, index: int) -> Tuple[Optional[str], Optional[cv2.VideoCapture]]:
        """Détecte le meilleur backend pour une caméra"""
        for backend_name, backend_id in self.BACKENDS.items():
            # Skip certains backends selon l'OS
            if self.os_type == "Windows" and backend_name in ["V4L2", "AVFoundation"]:
                continue
            elif self.os_type == "Linux" and backend_name in ["DirectShow", "MSMF", "AVFoundation"]:
                continue
            elif self.os_type == "Darwin" and backend_name in ["DirectShow", "MSMF", "V4L2"]:
                continue
                
            try:
                cap = cv2.VideoCapture(index, backend_id)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        return backend_name, cap
                    cap.release()
            except:
                pass
                
        return None, None
    
    def get_camera_properties(self, cap: cv2.VideoCapture) -> Dict:
        """Récupère toutes les propriétés disponibles d'une caméra"""
        properties = {}
        
        for prop_name, prop_id in self.PROPERTIES.items():
            try:
                value = cap.get(prop_id)
                if value != -1:  # -1 signifie non supporté
                    if prop_name == "Codec":
                        # Convertir FOURCC en string
                        fourcc = int(value)
                        codec = "".join([chr((fourcc >> 8 * i) & 0xFF) for i in range(4)])
                        properties[prop_name] = codec
                    else:
                        properties[prop_name] = value
            except:
                pass
                
        return properties
    
    def test_resolutions(self, cap: cv2.VideoCapture, index: int) -> List[Tuple[int, int]]:
        """Teste les résolutions supportées"""
        supported = []
        original_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        original_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        
        for width, height in self.COMMON_RESOLUTIONS:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
            
            actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            
            if actual_width == width and actual_height == height:
                # Vérifier que la résolution fonctionne vraiment
                ret, frame = cap.read()
                if ret and frame is not None:
                    if frame.shape[1] == width and frame.shape[0] == height:
                        supported.append((width, height))
        
        # Restaurer la résolution originale
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, original_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, original_height)
        
        return supported
    
    def get_windows_camera_info(self) -> Dict[int, Dict]:
        """Récupère des infos supplémentaires sous Windows via WMI"""
        camera_info = {}
        
        if not WINDOWS_EXTRAS or self.os_type != "Windows":
            return camera_info
            
        try:
            c = wmi.WMI()
            # Recherche des périphériques d'imagerie
            for item in c.Win32_PnPEntity():
                if item.Caption and ("camera" in item.Caption.lower() or 
                                   "webcam" in item.Caption.lower() or
                                   "imaging" in item.Caption.lower()):
                    info = {
                        "name": item.Caption,
                        "device_id": item.DeviceID,
                        "manufacturer": item.Manufacturer,
                        "status": item.Status,
                        "pnp_class": item.PNPClass
                    }
                    # Essayer de mapper avec un index (approximatif)
                    for i in range(10):
                        if i not in camera_info:
                            camera_info[i] = info
                            break
        except Exception as e:
            print(f"Erreur WMI: {e}")
            
        return camera_info
    
    def scan_sources(self, max_index: int = 10, callback=None) -> List[VideoSource]:
        """Scanne toutes les sources vidéo disponibles"""
        self.sources = []
        self.scanning = True
        
        # Infos Windows supplémentaires
        windows_info = self.get_windows_camera_info()
        
        for index in range(max_index):
            if not self.scanning:
                break
                
            source = VideoSource(index)
            
            # Mise à jour du callback
            if callback:
                callback(f"Test de l'index {index}...")
            
            # Détecter le meilleur backend
            backend_name, cap = self.detect_backend(index)
            
            if cap is not None:
                source.is_available = True
                source.backend = backend_name
                
                # Nom de la caméra
                if index in windows_info:
                    source.name = windows_info[index]["name"]
                else:
                    source.name = f"Camera {index} ({backend_name})"
                
                # Propriétés
                source.properties = self.get_camera_properties(cap)
                
                # Résolution actuelle
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                source.current_resolution = (width, height)
                source.current_fps = cap.get(cv2.CAP_PROP_FPS)
                
                # Test des résolutions (optionnel car peut être lent)
                if callback:
                    callback(f"Test des résolutions pour {source.name}...")
                source.supported_resolutions = self.test_resolutions(cap, index)
                
                # Capture d'un frame pour l'aperçu
                ret, frame = cap.read()
                if ret and frame is not None:
                    source.last_frame = frame.copy()
                
                cap.release()
            else:
                source.error_message = "Aucun backend compatible trouvé"
            
            self.sources.append(source)
            
            if callback:
                callback(f"Source {index}: {'✓' if source.is_available else '✗'}")
        
        self.scanning = False
        return self.sources
    
    def stop_scanning(self):
        """Arrête le scan en cours"""
        self.scanning = False

class VideoPreviewWidget(tk.Frame):
    """Widget pour afficher l'aperçu vidéo"""
    
    def __init__(self, parent, source: VideoSource, width=320, height=240):
        super().__init__(parent)
        self.source = source
        self.width = width
        self.height = height
        self.cap = None
        self.running = False
        self.thread = None
        
        self.setup_ui()
        
    def setup_ui(self):
        """Configure l'interface du widget"""
        # Titre
        title = tk.Label(self, text=self.source.name, font=("Arial", 10, "bold"))
        title.pack(pady=5)
        
        # Canvas pour l'image
        self.canvas = tk.Canvas(self, width=self.width, height=self.height, bg="black")
        self.canvas.pack()
        
        # Infos basiques
        info_text = f"Index: {self.source.index} | Backend: {self.source.backend}"
        if self.source.current_resolution:
            info_text += f" | {self.source.current_resolution[0]}x{self.source.current_resolution[1]}"
        
        self.info_label = tk.Label(self, text=info_text, font=("Arial", 8))
        self.info_label.pack()
        
        # Boutons
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=5)
        
        self.start_btn = tk.Button(btn_frame, text="▶ Démarrer", command=self.toggle_preview)
        self.start_btn.pack(side=tk.LEFT, padx=2)
        
        self.details_btn = tk.Button(btn_frame, text="📋 Détails", command=self.show_details)
        self.details_btn.pack(side=tk.LEFT, padx=2)
        
    def toggle_preview(self):
        """Active/désactive l'aperçu en temps réel"""
        if self.running:
            self.stop_preview()
        else:
            self.start_preview()
    
    def start_preview(self):
        """Démarre l'aperçu vidéo"""
        if not self.source.is_available:
            return
            
        self.running = True
        self.start_btn.config(text="⏸ Arrêter")
        
        # Ouvrir la caméra
        backend_id = VideoScanner.BACKENDS.get(self.source.backend, cv2.CAP_ANY)
        self.cap = cv2.VideoCapture(self.source.index, backend_id)
        
        # Thread pour la capture
        self.thread = threading.Thread(target=self.capture_loop, daemon=True)
        self.thread.start()
    
    def stop_preview(self):
        """Arrête l'aperçu vidéo"""
        self.running = False
        self.start_btn.config(text="▶ Démarrer")
        
        if self.cap:
            self.cap.release()
            self.cap = None
            
        # Effacer le canvas
        self.canvas.delete("all")
        self.canvas.create_text(self.width//2, self.height//2, text="Aperçu arrêté", 
                               fill="white", font=("Arial", 12))
    
    def capture_loop(self):
        """Boucle de capture vidéo"""
        fps_counter = 0
        fps_start = time.time()
        current_fps = 0
        
        while self.running and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                time.sleep(0.1)
                continue
            
            # Calcul FPS
            fps_counter += 1
            if fps_counter >= 10:
                current_fps = fps_counter / (time.time() - fps_start)
                fps_counter = 0
                fps_start = time.time()
            
            # Redimensionner pour l'aperçu
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w = frame.shape[:2]
            
            # Calculer le ratio pour fit dans le canvas
            ratio = min(self.width/w, self.height/h)
            new_w, new_h = int(w*ratio), int(h*ratio)
            
            frame_resized = cv2.resize(frame_rgb, (new_w, new_h))
            
            # Ajouter infos sur l'image
            cv2.putText(frame_resized, f"FPS: {current_fps:.1f}", (10, 20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Convertir en PhotoImage
            image = Image.fromarray(frame_resized)
            photo = ImageTk.PhotoImage(image=image)
            
            # Mettre à jour le canvas
            self.canvas.delete("all")
            self.canvas.create_image(self.width//2, self.height//2, image=photo)
            self.canvas.image = photo  # Garder une référence
            
            # Limiter le framerate
            time.sleep(0.033)  # ~30 FPS
    
    def show_details(self):
        """Affiche les détails complets de la source"""
        details_window = tk.Toplevel(self)
        details_window.title(f"Détails - {self.source.name}")
        details_window.geometry("600x500")
        
        # Text widget avec scrollbar
        text_frame = tk.Frame(details_window)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        scrollbar = tk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        text_widget = tk.Text(text_frame, wrap=tk.WORD, yscrollcommand=scrollbar.set)
        text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=text_widget.yview)
        
        # Remplir avec les infos
        text_widget.insert(tk.END, f"=== {self.source.name} ===\n\n")
        text_widget.insert(tk.END, f"Index: {self.source.index}\n")
        text_widget.insert(tk.END, f"Backend: {self.source.backend}\n")
        text_widget.insert(tk.END, f"Disponible: {'Oui' if self.source.is_available else 'Non'}\n")
        
        if self.source.current_resolution:
            text_widget.insert(tk.END, f"\nRésolution actuelle: {self.source.current_resolution[0]}x{self.source.current_resolution[1]}\n")
            text_widget.insert(tk.END, f"FPS: {self.source.current_fps:.1f}\n")
        
        if self.source.properties:
            text_widget.insert(tk.END, "\n=== Propriétés ===\n")
            for prop, value in self.source.properties.items():
                text_widget.insert(tk.END, f"{prop}: {value}\n")
        
        if self.source.supported_resolutions:
            text_widget.insert(tk.END, "\n=== Résolutions supportées ===\n")
            for w, h in self.source.supported_resolutions:
                text_widget.insert(tk.END, f"- {w}x{h}\n")
        
        # JSON complet
        text_widget.insert(tk.END, "\n=== Export JSON ===\n")
        json_data = json.dumps(self.source.to_dict(), indent=2)
        text_widget.insert(tk.END, json_data)
        
        # Bouton pour copier
        copy_btn = tk.Button(details_window, text="📋 Copier JSON", 
                           command=lambda: self.copy_to_clipboard(json_data))
        copy_btn.pack(pady=5)
        
        text_widget.config(state=tk.DISABLED)
    
    def copy_to_clipboard(self, text):
        """Copie le texte dans le presse-papiers"""
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()

class VideoScannerGUI:
    """Interface graphique principale"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Scanner d'Entrées Vidéo - Aperçu Temps Réel")
        self.root.geometry("1200x800")
        
        self.scanner = VideoScanner()
        self.preview_widgets = []
        
        self.setup_ui()
        
    def setup_ui(self):
        """Configure l'interface principale"""
        # Frame supérieure pour les contrôles
        control_frame = tk.Frame(self.root)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Infos système
        os_info = f"OS: {platform.system()} {platform.release()}"
        tk.Label(control_frame, text=os_info, font=("Arial", 10)).pack(side=tk.LEFT, padx=10)
        
        # Boutons de contrôle
        self.scan_btn = tk.Button(control_frame, text="🔍 Scanner les caméras", 
                                command=self.start_scan, bg="#4CAF50", fg="white",
                                font=("Arial", 10, "bold"))
        self.scan_btn.pack(side=tk.LEFT, padx=5)
        
        self.stop_btn = tk.Button(control_frame, text="⏹ Arrêter le scan", 
                                command=self.stop_scan, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)
        
        self.export_btn = tk.Button(control_frame, text="💾 Exporter rapport", 
                                  command=self.export_report)
        self.export_btn.pack(side=tk.LEFT, padx=5)
        
        # Spinbox pour le nombre max de caméras
        tk.Label(control_frame, text="Max caméras:").pack(side=tk.LEFT, padx=(20, 5))
        self.max_cameras = tk.Spinbox(control_frame, from_=1, to=20, width=5)
        self.max_cameras.delete(0, tk.END)
        self.max_cameras.insert(0, "10")
        self.max_cameras.pack(side=tk.LEFT)
        
        # Frame pour le statut
        status_frame = tk.Frame(self.root)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.status_label = tk.Label(status_frame, text="Prêt à scanner", 
                                   font=("Arial", 10), anchor=tk.W)
        self.status_label.pack(side=tk.LEFT)
        
        # Progress bar
        self.progress = ttk.Progressbar(status_frame, mode='indeterminate')
        self.progress.pack(side=tk.RIGHT, padx=10)
        
        # Frame scrollable pour les aperçus
        self.create_scrollable_frame()
        
    def create_scrollable_frame(self):
        """Crée une frame scrollable pour les aperçus"""
        # Canvas et scrollbar
        canvas = tk.Canvas(self.root)
        scrollbar = tk.Scrollbar(self.root, orient="vertical", command=canvas.yview)
        self.scrollable_frame = tk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        scrollbar.pack(side="right", fill="y")
        
        # Bind mouse wheel
        def on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)
    
    def update_status(self, message: str):
        """Met à jour le statut"""
        self.status_label.config(text=message)
        self.root.update()
    
    def start_scan(self):
        """Démarre le scan des caméras"""
        # Nettoyer les aperçus existants
        for widget in self.preview_widgets:
            widget.stop_preview()
            widget.destroy()
        self.preview_widgets = []
        
        # Configuration UI
        self.scan_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.progress.start(10)
        
        # Lancer le scan dans un thread
        max_cams = int(self.max_cameras.get())
        thread = threading.Thread(target=self.scan_thread, args=(max_cams,), daemon=True)
        thread.start()
    
    def scan_thread(self, max_cameras: int):
        """Thread pour le scan"""
        sources = self.scanner.scan_sources(max_cameras, callback=self.update_status)
        
        # Créer les widgets d'aperçu
        self.root.after(0, self.create_preview_widgets, sources)
    
    def create_preview_widgets(self, sources: List[VideoSource]):
        """Crée les widgets d'aperçu pour chaque source"""
        # Filtrer les sources disponibles
        available_sources = [s for s in sources if s.is_available]
        
        if not available_sources:
            self.update_status("Aucune caméra trouvée")
        else:
            self.update_status(f"{len(available_sources)} caméra(s) trouvée(s)")
        
        # Créer les widgets en grille
        row, col = 0, 0
        max_cols = 3
        
        for source in available_sources:
            frame = tk.Frame(self.scrollable_frame, relief=tk.RAISED, borderwidth=1)
            frame.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
            
            preview = VideoPreviewWidget(frame, source)
            preview.pack(padx=10, pady=10)
            self.preview_widgets.append(preview)
            
            col += 1
            if col >= max_cols:
                col = 0
                row += 1
        
        # Arrêter la progress bar
        self.progress.stop()
        self.scan_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
    
    def stop_scan(self):
        """Arrête le scan en cours"""
        self.scanner.stop_scanning()
        self.progress.stop()
        self.scan_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.update_status("Scan arrêté")
    
    def export_report(self):
        """Exporte un rapport complet"""
        if not self.scanner.sources:
            self.update_status("Aucune donnée à exporter")
            return
        
        # Créer le rapport
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"video_sources_report_{timestamp}.json"
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "system": {
                "os": platform.system(),
                "os_version": platform.version(),
                "python_version": platform.python_version(),
                "opencv_version": cv2.__version__
            },
            "sources": [s.to_dict() for s in self.scanner.sources]
        }
        
        # Sauvegarder
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            
            self.update_status(f"Rapport exporté : {filename}")
            
            # Ouvrir le fichier (Windows)
            if platform.system() == "Windows":
                os.startfile(filename)
        except Exception as e:
            self.update_status(f"Erreur export : {e}")
    
    def run(self):
        """Lance l'application"""
        self.root.mainloop()

def main():
    """Fonction principale"""
    print("🎥 Scanner d'Entrées Vidéo avec Aperçu Temps Réel")
    print("=" * 50)
    
    # Mode console ou GUI
    if len(sys.argv) > 1 and sys.argv[1] == "--console":
        # Mode console simple
        scanner = VideoScanner()
        print("Scan en cours...")
        sources = scanner.scan_sources(10, callback=print)
        
        print(f"\n{len([s for s in sources if s.is_available])} caméra(s) trouvée(s):")
        for source in sources:
            if source.is_available:
                print(f"\n- {source.name}")
                print(f"  Index: {source.index}")
                print(f"  Backend: {source.backend}")
                print(f"  Résolution: {source.current_resolution}")
                print(f"  FPS: {source.current_fps}")
    else:
        # Mode GUI
        app = VideoScannerGUI()
        app.run()

if __name__ == "__main__":
    main()