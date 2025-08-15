import cv2
import os
from datetime import datetime

def capture_image():
    """Capture une image depuis la webcam et la sauvegarde"""
    
    # Initialiser la webcam (0 = caméra par défaut)
    cap = cv2.VideoCapture(0)
    
    # Vérifier si la caméra s'ouvre correctement
    if not cap.isOpened():
        print("Erreur: Impossible d'ouvrir la webcam")
        print("Vérifiez que votre caméra est connectée et non utilisée par une autre application")
        return False
    
    # Optionnel: Définir la résolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    print("Webcam initialisée avec succès")
    print("Appuyez sur 'ESPACE' pour capturer une image")
    print("Appuyez sur 'q' pour quitter")
    
    # Créer le dossier de sauvegarde s'il n'existe pas
    save_folder = "captured_images"
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)
        print(f"Dossier '{save_folder}' créé")
    
    image_count = 0
    
    while True:
        # Lire une frame depuis la webcam
        ret, frame = cap.read()
        
        if not ret:
            print("Erreur: Impossible de lire depuis la webcam")
            break
        
        # Afficher la frame en temps réel
        cv2.imshow('Webcam - Appuyez sur ESPACE pour capturer', frame)
        
        # Attendre une touche
        key = cv2.waitKey(1) & 0xFF
        
        # Capturer l'image si ESPACE est pressé
        if key == ord(' '):
            # Générer un nom de fichier unique avec timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{save_folder}/capture_{timestamp}_{image_count:03d}.jpg"
            
            # Sauvegarder l'image
            success = cv2.imwrite(filename, frame)
            
            if success:
                image_count += 1
                print(f"✅ Image sauvegardée: {filename}")
                
                # Effet visuel de capture (flash blanc)
                flash_frame = frame.copy()
                flash_frame.fill(255)
                cv2.imshow('Webcam - Appuyez sur ESPACE pour capturer', flash_frame)
                cv2.waitKey(100)  # Afficher le flash pendant 100ms
            else:
                print(f"❌ Erreur lors de la sauvegarde de {filename}")
        
        # Quitter si 'q' est pressé
        elif key == ord('q'):
            print("Fermeture de l'application...")
            break
    
    # Libérer les ressources
    cap.release()
    cv2.destroyAllWindows()
    
    print(f"Session terminée. {image_count} image(s) capturée(s)")
    return True

def capture_single_image():
    """Version simplifiée pour capturer une seule image rapidement"""
    
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("Erreur: Impossible d'ouvrir la webcam")
        return False
    
    print("Capture en cours...")
    
    # Lire quelques frames pour stabiliser la caméra
    for i in range(5):
        ret, frame = cap.read()
        if not ret:
            print("Erreur lors de la lecture de la webcam")
            cap.release()
            return False
    
    # Capturer l'image finale
    ret, frame = cap.read()
    if ret:
        # Créer le dossier s'il n'existe pas
        save_folder = "captured_images"
        if not os.path.exists(save_folder):
            os.makedirs(save_folder)
        
        # Nom de fichier avec timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{save_folder}/quick_capture_{timestamp}.jpg"
        
        # Sauvegarder
        success = cv2.imwrite(filename, frame)
        
        if success:
            print(f"✅ Image capturée et sauvegardée: {filename}")
        else:
            print(f"❌ Erreur lors de la sauvegarde")
    
    cap.release()
    return True

def capture_with_preview():
    """Version avec prévisualisation et meilleure interface"""
    
    cap = cv2.VideoCapture(1)
    
    if not cap.isOpened():
        print("Erreur: Impossible d'ouvrir la webcam")
        return False
    
    # Améliorer la qualité d'image
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    # Créer le dossier de sauvegarde
    save_folder = "captured_images"
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)
    
    print("=== CAPTURE D'IMAGE WEBCAM ===")
    print("Contrôles:")
    print("  ESPACE - Capturer une image")
    print("  s      - Sauvegarder sans prévisualisation")
    print("  f      - Plein écran")
    print("  r      - Changer la résolution")
    print("  q      - Quitter")
    print()
    
    image_count = 0
    fullscreen = False
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # Ajouter des informations sur l'image
        height, width = frame.shape[:2]
        
        # Afficher les informations en overlay
        cv2.putText(frame, f"Resolution: {width}x{height}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, f"Images capturees: {image_count}", (10, 60), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.putText(frame, "ESPACE = Capturer | Q = Quitter", (10, height - 20), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Afficher la frame
        window_name = 'Webcam Capture'
        cv2.imshow(window_name, frame)
        
        # Gestion des touches
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord(' '):
            # Capture avec effet visuel
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{save_folder}/capture_{timestamp}_{image_count:03d}.jpg"
            
            # Effet de flash
            flash_frame = frame.copy()
            cv2.rectangle(flash_frame, (0, 0), (width, height), (255, 255, 255), 20)
            cv2.imshow(window_name, flash_frame)
            cv2.waitKey(150)
            
            # Sauvegarder l'image originale
            success = cv2.imwrite(filename, frame)
            if success:
                image_count += 1
                print(f"✅ Image {image_count} sauvegardée: {filename}")
            else:
                print(f"❌ Erreur lors de la sauvegarde")
        
        elif key == ord('s'):
            # Sauvegarde rapide sans effet
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{save_folder}/quick_{timestamp}.jpg"
            if cv2.imwrite(filename, frame):
                image_count += 1
                print(f"💾 Sauvegarde rapide: {filename}")
        
        elif key == ord('f'):
            # Toggle plein écran
            fullscreen = not fullscreen
            if fullscreen:
                cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            else:
                cv2.setWindowProperty(window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
        
        elif key == ord('r'):
            # Changer la résolution
            current_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            if current_width == 640:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                print("Résolution changée: 1280x720")
            else:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                print("Résolution changée: 640x480")
        
        elif key == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
    print(f"\nSession terminée. Total: {image_count} image(s) capturée(s)")

if __name__ == "__main__":
    print("Choisissez le mode de capture:")
    print("1. Mode interactif avec prévisualisation (recommandé)")
    print("2. Mode simple (ESPACE pour capturer)")
    print("3. Capture rapide d'une seule image")
    
    try:
        choice = input("Votre choix (1-3): ").strip()
        
        if choice == "1":
            capture_with_preview()
        elif choice == "2":
            capture_image()
        elif choice == "3":
            capture_single_image()
        else:
            print("Choix invalide, utilisation du mode par défaut...")
            capture_with_preview()
            
    except KeyboardInterrupt:
        print("\nArrêt demandé par l'utilisateur")
    except Exception as e:
        print(f"Erreur: {e}")