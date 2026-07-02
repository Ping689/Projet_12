import os
import sys
import shutil
import socket
import argparse
from pathlib import Path

def restart_container(container_name):
    print(f"Envoi de la requête de redémarrage pour le conteneur '{container_name}'...")
    socket_path = "/var/run/docker.sock"
    if not os.path.exists(socket_path):
        print(f"Erreur : Le socket Docker '{socket_path}' n'est pas accessible depuis ce conteneur.")
        return False
    
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.connect(socket_path)
        request = f"POST /containers/{container_name}/restart HTTP/1.1\r\nHost: localhost\r\n\r\n"
        s.sendall(request.encode('utf-8'))
        response = s.recv(1024).decode('utf-8')
        s.close()
        
        if "HTTP/1.1 204" in response or "HTTP/1.1 200" in response:
            print(f"Succès : Le conteneur '{container_name}' a été redémarré.")
            return True
        else:
            print(f"Réponse inattendue du démon Docker : {response}")
            return False
    except Exception as e:
        print(f"Erreur lors de la communication avec le démon Docker : {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Synchronise la prime sportive entre Kestra et Spark Streaming.")
    parser.add_argument("--pct", type=float, required=True, help="Le nouveau pourcentage de la prime (ex: 0.08)")
    args = parser.parse_args()

    # Déterminer la racine du projet
    # Si on tourne dans Docker Kestra, la racine est /workspace
    # Sinon, on prend le dossier parent du script
    base_dir = Path("/workspace") if Path("/workspace").exists() else Path(__file__).resolve().parents[1]
    env_file = base_dir / ".env"
    outputs_dir = base_dir / "outputs"

    print(f"Racine du projet identifiée : {base_dir}")

    # 1. Mise à jour du fichier .env
    if env_file.exists():
        print(f"Mise à jour du fichier {env_file}...")
        content = env_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        updated = False
        
        for i, line in enumerate(lines):
            if line.startswith("SPORT_PRIME_PCT="):
                lines[i] = f"SPORT_PRIME_PCT={args.pct}"
                updated = True
                break
                
        if not updated:
            lines.append(f"SPORT_PRIME_PCT={args.pct}")
            
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Variable SPORT_PRIME_PCT mise à jour à {args.pct} dans le fichier .env.")
    else:
        print(f"Avertissement : Fichier {env_file} introuvable.")

    # 2. Suppression des checkpoints et des tables Delta pour forcer le recalcul
    folders_to_delete = [
        outputs_dir / "checkpoint_finance",
        outputs_dir / "delta_finance",
        outputs_dir / "delta_raw_activities"
    ]
    
    for folder in folders_to_delete:
        if folder.exists():
            print(f"Suppression du dossier {folder}...")
            try:
                shutil.rmtree(folder)
                print(f"Dossier {folder} supprimé avec succès.")
            except Exception as e:
                print(f"Erreur lors de la suppression de {folder} : {e}")

    # 3. Redémarrage du conteneur Spark Streaming
    restart_container("spark-streaming")

if __name__ == "__main__":
    main()
