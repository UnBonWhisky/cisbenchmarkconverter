from bs4 import BeautifulSoup
from datetime import datetime, timezone
import httpx
import os
import re
from typing import List, Dict, Tuple
from colorama import Fore, Style, init
from cis_benchmark_converter import read_pdf, extract_recommendations, write_output

# Initialize colorama for Windows
init(autoreset=True)

client = httpx.Client()
base_url = 'https://downloads.cisecurity.org'
page_url = base_url + '/'
technology_url = base_url + '/technology'
document_url = technology_url + '/{}/benchmarks/latest'
download_url = base_url + '/download'

def log_info(message):
    print(f"{Fore.GREEN}[INFO]{Style.RESET_ALL} {message}")
    
def log_debug(message):
    print(f"{Fore.BLUE}[DEBUG]{Style.RESET_ALL} {message}")

# Récupérer le token csrf pour les prochaines requetes
def grab_token() -> str:
    log_info("Grabbing CSRF token")
    response = client.get(page_url)
    soup = BeautifulSoup(response.text, 'html.parser')

    # get the meta tag csrf-token content
    csrf_token = soup.find('meta', {'name': 'csrf-token'})['content']
    log_debug(f"CSRF token: {csrf_token}")
    
    return csrf_token

# On requete la page technology pour récupérer les clés des documents
def get_json_keys() -> tuple[dict, str]:
    csrf_token = grab_token()
    
    log_info("Getting JSON document keys")
    
    headers = {
        'X-CSRF-Token': csrf_token,
        'X-Requested-With': 'XMLHttpRequest',
        'Referer': page_url
    }
    response = client.get(technology_url, headers=headers)
    json_data = response.json()
    return json_data, csrf_token

# On récupère les liens des documents avec le json de /technology
def make_document_links() -> list[list[str, str]]:
    
    json_data, csrf_token = get_json_keys()
    
    document_links = []
    for key in json_data.keys():
        for item in json_data[key]:
            document_links.append(item['id'])
    
    files_url = []
    for document in document_links:
        get_document_url = document_url.format(document)
        headers = {
            'X-CSRF-Token': csrf_token,
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': page_url
        }
        response = client.get(get_document_url, headers=headers)
        json_data = response.json()
        
        for i in range(len(json_data)):
            for doc_id in json_data[i]['documents']:
                files_url.append([doc_id['id'], doc_id['filename']])
    
    log_info(f"Found {len(files_url)} documents")
    
    return files_url

# Check des fichiers existants + déplacement des anciennes versions si nécessaire
def get_existing_files() -> Dict[str, List[Tuple[str, str]]]:
    existing_files = {}
    
    # On liste le dossier 'pdf'
    for filename in os.listdir('pdf'):
        if filename.endswith('.pdf'):
            clean_filename = filename
            
            # Si le fichier contient '_ARCHIVE', on le retire pour le traitement
            if '_ARCHIVE' in clean_filename:
                clean_filename = clean_filename.replace('_ARCHIVE', '')
            
            # On récupère le nom et la version du fichier au format
            # {benchmark_type}_v{version}.pdf
            version_match = re.search(r'(.+?)_v(\d+\.\d+\.\d+)\.pdf$', clean_filename)
            if version_match:
                benchmark_type = version_match.group(1)
                version = version_match.group(2)
                
                # Si le fichier n'est pas un existant dans notre dictionnaire, on l'ajoute au format :
                # {benchmark_type: [(filename, version, dossier_destination)]}
                if benchmark_type not in existing_files:
                    existing_files[benchmark_type] = []
                existing_files[benchmark_type].append((filename, version, 'pdf'))
    
    # On scan le dossier d'archive
    for filename in os.listdir('pdf_archive'):
        if filename.endswith('.pdf'):
            clean_filename = filename
            
            # Si le fichier contient '_ARCHIVE', on le retire pour le traitement
            if '_ARCHIVE' in clean_filename:
                clean_filename = clean_filename.replace('_ARCHIVE', '')
            
            # On récupère le nom et la version du fichier au format
            # {benchmark_type}_v{version}.pdf
            version_match = re.search(r'(.+?)_v(\d+\.\d+\.\d+)\.pdf$', clean_filename)
            if version_match:
                benchmark_type = version_match.group(1)
                version = version_match.group(2)
                
                # Si le fichier n'est pas un existant dans notre dictionnaire, on l'ajoute au format :
                # {benchmark_type: [(filename, version, dossier_destination)]}
                if benchmark_type not in existing_files:
                    existing_files[benchmark_type] = []
                existing_files[benchmark_type].append((filename, version, 'pdf_archive'))
    
    return existing_files

# On fait un filtre pour déterminer quels fichiers télécharger et où les placer
def filter_files(files_url: list[list[str, str]]) -> list[list[str, str, str, bool]]:
    
    # Clean filenames and extract version info
    cleaned_files = []
    
    for file_id, filename in files_url:
        # On renomme les fichiers qui finissent en ' PDF.pdf' pour mettre '.pdf'
        if filename.endswith(' PDF.pdf'):
            filename = filename.replace(' PDF.pdf', '.pdf')
        
        # Pour le process du fichier, on supprime le '_ARCHIVE' s'il est présent
        clean_filename = filename
        if '_ARCHIVE' in clean_filename:
            clean_filename = clean_filename.replace('_ARCHIVE', '')
            
        # On récupère le nom et la version du fichier au format
        # {benchmark_type}_v{version}.pdf
        version_match = re.search(r'(.+?)_v(\d+\.\d+\.\d+)\.pdf$', clean_filename)
        if version_match:
            benchmark_type = version_match.group(1)
            version = version_match.group(2)
            # On ajoute les informations dans notre liste
            cleaned_files.append([file_id, clean_filename, benchmark_type, version])
    
    # On regroupe les fichiers par nom de "benchmark_type" (nom du fichier avant la version)
    benchmark_groups = {}
    for file_info in cleaned_files:
        benchmark_type = file_info[2]
        if benchmark_type not in benchmark_groups:
            benchmark_groups[benchmark_type] = []
        benchmark_groups[benchmark_type].append(file_info)
    
    # On récupère les fichiers déjà existants
    existing_files = get_existing_files()
    
    # Pour chaque groupe dans les fichiers retrouvés par API
    result_files = []
    for benchmark_type, files in benchmark_groups.items():
        # On trie les fichiers par version
        files.sort(key=lambda x: [int(n) for n in x[3].split('.')], reverse=True)
        
        # Dernière version disponible
        latest = files[0]
        latest_version = latest[3]
        need_to_download_latest = True
        
        # On check si on a déjà le fichier dans notre dossier
        if benchmark_type in existing_files:
            existing_versions = existing_files[benchmark_type]
            
            # On déplace les anciennes versions dans le dossier d'archive si nécessaire
            latest_version_nums = [int(n) for n in latest_version.split('.')]
            
            for existing_name, existing_ver, existing_dir in existing_versions:
                existing_ver_nums = [int(n) for n in existing_ver.split('.')]
                
                # Si la version existante est plus ancienne que la dernière version
                # On déplace le fichier dans le dossier d'archive
                if compare_versions(existing_ver_nums, latest_version_nums) < 0 and existing_dir == 'pdf':
                    old_path = os.path.join('pdf', existing_name)
                    if '_ARCHIVE' not in existing_name:
                        new_filename = existing_name.replace('.pdf', '_ARCHIVE.pdf')
                    else:
                        new_filename = existing_name
                    new_path = os.path.join('pdf_archive', new_filename)
                    
                    log_debug(f"Moving older version: {existing_name} to pdf_archive/{new_filename}")
                    if os.path.exists(old_path) and not os.path.exists(new_path):
                        os.rename(old_path, new_path)
                    
                    log_debug(f"Removing csv/{existing_name}.csv")
                    if os.path.isfile(f"csv/{existing_name}.csv"):
                        os.remove(f"csv/{existing_name}.csv")
            
            # On fetch la dernière version existante pour comparer avec la dernière version disponible
            existing_versions.sort(key=lambda x: [int(n) for n in x[1].split('.')], reverse=True)
            highest_existing = existing_versions[0]
            highest_existing_version = highest_existing[1]
            highest_existing_nums = [int(n) for n in highest_existing_version.split('.')]
            
            if compare_versions(latest_version_nums, highest_existing_nums) <= 0:
                # Si on a déjà la dernière version, on ne la télécharge pas
                need_to_download_latest = False
        
        # Si on a besoin de télécharger la dernière version
        if need_to_download_latest:
            result_files.append([latest[0], latest[1], 'pdf', True])
        
        # Les anciennes versions on les télécharge uniquement si on les a pas dans notre dossier d'archive
        for old_file in files[1:]:
            file_id, clean_filename, benchmark_type, version = old_file
            archive_filename = clean_filename.replace('.pdf', '_ARCHIVE.pdf')
            
            need_to_download = True
            if benchmark_type in existing_files:
                for existing_name, existing_ver, existing_dir in existing_files[benchmark_type]:
                    if version == existing_ver:
                        need_to_download = False
                        break
            
            if need_to_download:
                result_files.append([file_id, archive_filename, 'pdf_archive', True])
    
    return result_files

def compare_versions(version1, version2):
    """Compare two version arrays and return:
    -1 if version1 < version2
     0 if version1 == version2
     1 if version1 > version2
    """
    # On s'assure que les deux versions ont la même longueur
    while len(version1) < len(version2):
        version1.append(0)
    while len(version2) < len(version1):
        version2.append(0)
    
    # On compare chaque version
    for v1, v2 in zip(version1, version2):
        if v1 < v2:
            return -1
        if v1 > v2:
            return 1
    
    # Si les versions sont les mêmes
    return 0

# On télécharge les fichiers
def download_files() -> None:
    files_url = make_document_links() # avec les clés des documents, on récupère les liens des documents
    filtered_files = filter_files(files_url) # on filtre les fichiers pour déterminer lesquels télécharger et où les placer
    current_time = datetime.now(timezone.utc).timestamp() # On génère un timestamp nécessaire pour pouvoir télécharger les fichiers
    download_link = download_url + f'?u={current_time}' # le lien de download est '/download?u={timestamp}'
    
    files_downloaded = 0
    for file in filtered_files:
        file_id, filename, directory, should_download = file
        
        # Si on a besoin de télécharger le fichier
        if should_download:
            print('\n', end='')
            log_debug(f"Downloading: {filename} to {directory}/")
            
            # On set notre header documentId avec l'id du fichier à télécharger
            headers = {
                "Cookie": f"documentId={file_id}"
            }
            response = client.get(download_link, headers=headers)
            
            # On ouvre le fichier en écriture binaire et on écrit le contenu de la réponse
            with open(f'{directory}/{filename}', 'wb') as f:
                f.write(response.content)
            files_downloaded += 1
            
            # Si c'est un pdf, on le traite pour générer le markdown et le csv
            if directory == 'pdf':
                input_file = f"pdf/{filename}"
                output_file = f"csv/{filename.replace('.pdf', '.csv')}"
                text = read_pdf(input_file)
                recommendations = extract_recommendations(text)
                write_output(
                    recommendations,
                    output_file,
                    input_file,
                )
                
    
    log_info(f"Downloaded {files_downloaded} files")

if __name__ == '__main__':
    
    if not os.path.exists('pdf'):
        os.mkdir('pdf')
    if not os.path.exists('pdf_archive'):
        os.mkdir('pdf_archive')
    if not os.path.exists('csv'):
        os.mkdir('csv')
        
    download_files()
