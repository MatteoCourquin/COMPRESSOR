import os
import subprocess
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
import multiprocessing

def format_filename(filename):
    """Formater le nom de fichier en minuscules et remplacer les caractères spéciaux"""
    formatted = filename.lower()
    formatted = formatted.replace(' ', '-')
    formatted = ''.join(c for c in formatted if c.isalnum() or c in '-_')
    return formatted

def get_video_size_mb(file_path):
    """Obtenir la taille du fichier en MB"""
    return os.path.getsize(file_path) / (1024 * 1024)

def get_supported_formats():
    """Liste des formats de fichiers vidéo supportés"""
    return ['.mp4', '.mov', '.m4v', '.avi', '.mkv', '.webm']

def get_video_info(input_file):
    """Obtenir les informations détaillées de la vidéo"""
    cmd = [
        'ffprobe',
        '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,duration',
        '-of', 'json',
        input_file
    ]
    try:
        output = subprocess.check_output(cmd).decode()
        import json
        info = json.loads(output)
        stream_info = info.get('streams', [{}])[0]
        return {
            'width': int(stream_info.get('width', 0)),
            'height': int(stream_info.get('height', 0)),
            'duration': float(stream_info.get('duration', 0))
        }
    except:
        return None

def calculate_target_bitrate(duration_seconds):
    """Calculer un bitrate cible basé sur la durée pour le format 1080x1920"""
    base_bitrate = 3000000  # 3Mbps base pour meilleure qualité vidéo
    target_size_mb = min(12, duration_seconds * 0.2)  # 0.2MB/s, max 12MB
    target_size_bits = target_size_mb * 8 * 1024 * 1024
    return min(int(target_size_bits / duration_seconds), base_bitrate)

def process_video(args):
    """Traiter une vidéo unique avec compression agressive pour le web"""
    input_file, output_dir = args
    input_path = Path(input_file)
    filename = format_filename(input_path.stem)
    
    mp4_output_dir = Path(output_dir) / "mp4"
    webm_output_dir = Path(output_dir) / "webm"
    mp4_output_dir.mkdir(parents=True, exist_ok=True)
    webm_output_dir.mkdir(parents=True, exist_ok=True)
    
    mp4_output = mp4_output_dir / f"{filename}.mp4"
    webm_output = webm_output_dir / f"{filename}.webm"
    
    print(f"\nTraitement de {input_file}...")
    
    # Obtenir les informations détaillées de la vidéo
    video_info = get_video_info(input_file)
    if not video_info:
        print(f"Erreur : Impossible d'obtenir les informations pour {input_file}")
        return
    
    file_size_mb = get_video_size_mb(input_file)
    duration = video_info['duration']
    
    # Calculer le bitrate optimal et le nombre de threads
    target_bitrate = calculate_target_bitrate(duration)
    ffmpeg_threads = max(1, multiprocessing.cpu_count() // 2)
    
    print(f"Bitrate cible : {target_bitrate/1024:.0f}kbps")
    
    # # Construction du filtre de redimensionnement
    # scale_filter = (
    #     f"scale=1080:1920:force_original_aspect_ratio=increase,"
    #     f"crop=1080:1920"
    # )
    
    try:
        # Commande MP4 optimisée pour meilleure qualité vidéo
        mp4_cmd = [
            'ffmpeg', '-y',
            '-i', str(input_file),
            '-threads', str(ffmpeg_threads),
            # '-vf', f'{scale_filter},format=yuv420p',
            '-c:v', 'libx264',
            '-crf', '20',
            '-preset', 'medium',
            '-profile:v', 'main',
            '-level', '4.0',
            '-maxrate', f'{target_bitrate}',
            '-bufsize', f'{target_bitrate*2}',
            '-movflags', '+faststart',
            '-color_primaries', 'bt709',
            '-color_trc', 'bt709',
            '-colorspace', 'bt709',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-ar', '48000',
            str(mp4_output)
        ]
        
        result = subprocess.run(mp4_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print("Erreur MP4:", result.stderr)
            raise subprocess.CalledProcessError(result.returncode, mp4_cmd, result.stdout, result.stderr)

        # Si le MP4 est créé avec succès, créer le WebM avec meilleure qualité vidéo
        if mp4_output.exists():
            webm_cmd = [
                'ffmpeg', '-y',
                '-i', str(mp4_output),
                '-threads', str(ffmpeg_threads),
                '-c:v', 'libvpx-vp9',
                '-b:v', f'{int(target_bitrate*0.9)}',
                '-minrate', f'{int(target_bitrate*0.6)}',
                '-maxrate', f'{target_bitrate}',
                '-tile-columns', '2',
                '-frame-parallel', '1',
                '-speed', '1',  # Meilleure qualité d'encodage
                '-auto-alt-ref', '1',
                '-lag-in-frames', '25',
                '-g', '240',
                '-pix_fmt', 'yuv420p',
                '-c:a', 'libopus',
                '-b:a', '96k',  # Paramètres audio d'origine
                str(webm_output)
            ]
            
            result = subprocess.run(webm_cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print("Erreur WebM:", result.stderr)
                raise subprocess.CalledProcessError(result.returncode, webm_cmd, result.stdout, result.stderr)
            
            # Vérifier les tailles finales
            mp4_size = get_video_size_mb(mp4_output)
            webm_size = get_video_size_mb(webm_output)
            
            print(f"\nRésultats de compression:")
            print(f"Original: {file_size_mb:.2f}MB")
            print(f"MP4: {mp4_size:.2f}MB ({(mp4_size/file_size_mb)*100:.1f}%)")
            print(f"WebM: {webm_size:.2f}MB ({(webm_size/file_size_mb)*100:.1f}%)")
            
            # Si le WebM est plus grand que le MP4, on le recrée avec des paramètres ajustés
            if webm_size > mp4_size:
                print("Le WebM est plus grand que le MP4, nouvelle tentative avec bitrate réduit...")
                webm_cmd = [
                    'ffmpeg', '-y',
                    '-i', str(mp4_output),
                    '-threads', str(ffmpeg_threads),
                    '-c:v', 'libvpx-vp9',
                    '-b:v', f'{int(target_bitrate*0.7)}',
                    '-minrate', f'{int(target_bitrate*0.4)}',
                    '-maxrate', f'{int(target_bitrate*0.8)}',
                    '-tile-columns', '2',
                    '-frame-parallel', '1',
                    '-speed', '1',
                    '-auto-alt-ref', '1',
                    '-lag-in-frames', '25',
                    '-g', '240',
                    '-pix_fmt', 'yuv420p',
                    '-c:a', 'libopus',
                    '-b:a', '96k',  # Paramètres audio d'origine
                    str(webm_output)
                ]
                
                subprocess.run(webm_cmd, check=True, capture_output=True)
                webm_size = get_video_size_mb(webm_output)
                print(f"Nouveau WebM: {webm_size:.2f}MB ({(webm_size/file_size_mb)*100:.1f}%)")
            
            return {
                'filename': filename,
                'original_size': file_size_mb,
                'mp4_size': mp4_size,
                'webm_size': webm_size,
                'duration': duration,
                'success': True
            }
            
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors du traitement de {input_file}")
        print(f"Sortie d'erreur : {e.stderr if hasattr(e, 'stderr') else str(e)}")
        return {
            'filename': filename,
            'error': str(e),
            'success': False
        }

def batch_process_videos(input_dir, output_dir):
    """Traiter tous les fichiers vidéo en parallèle"""
    input_path = Path(input_dir)
    supported_formats = get_supported_formats()
    
    # Récupérer tous les fichiers du dossier
    all_files = list(input_path.glob("*"))
    
    # Filtrer les fichiers vidéo supportés
    video_files = [f for f in all_files if f.suffix.lower() in supported_formats]
    unsupported_files = [f for f in all_files if f not in video_files]
    
    if not video_files:
        print("Aucun fichier vidéo supporté trouvé dans le dossier d'entrée")
        return
    
    print("\n=== Analyse des fichiers ===")
    print(f"Nombre total de fichiers dans le dossier : {len(all_files)}")
    print(f"Fichiers vidéo supportés : {len(video_files)}")
    
    # Afficher les détails des formats trouvés
    format_count = {}
    for video in video_files:
        ext = video.suffix.lower()
        format_count[ext] = format_count.get(ext, 0) + 1
    
    print("\nDétail des formats trouvés :")
    for fmt, count in format_count.items():
        print(f"- {fmt}: {count} fichiers")
    
    if unsupported_files:
        print("\nFichiers ignorés :")
        for f in unsupported_files:
            print(f"- {f.name}")
    
    max_workers = max(1, multiprocessing.cpu_count() - 1)
    print(f"\nDémarrage du traitement avec {max_workers} processus en parallèle")
    print(f"Nombre total de vidéos à traiter : {len(video_files)}\n")
    
    process_args = [(str(video_file), output_dir) for video_file in video_files]
    
    results = []
    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(process_video, process_args))
    
    print("\n=== Résumé du traitement ===")
    successful = [r for r in results if r and r.get('success', False)]
    failed = [r for r in results if r and not r.get('success', False)]
    
    print(f"\nVidéos traitées avec succès: {len(successful)}")
    print(f"Échecs: {len(failed)}")
    
    if failed:
        print("\nFichiers en échec:")
        for result in failed:
            print(f"- {result['filename']}: {result.get('error', 'Erreur inconnue')}")
    
    if successful:
        total_original = sum(r['original_size'] for r in successful)
        total_mp4 = sum(r['mp4_size'] for r in successful)
        total_webm = sum(r['webm_size'] for r in successful)
        
        print(f"\nRéduction totale de taille:")
        print(f"Original: {total_original:.2f}MB")
        print(f"MP4: {total_mp4:.2f}MB (ratio: {(total_mp4/total_original)*100:.1f}%)")
        print(f"WebM: {total_webm:.2f}MB (ratio: {(total_webm/total_original)*100:.1f}%)")

if __name__ == "__main__":
    INPUT_DIR = "videos_input"
    OUTPUT_DIR = "videos_output"
    
    batch_process_videos(INPUT_DIR, OUTPUT_DIR)