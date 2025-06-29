from flask import Flask, request, jsonify
from huggingface_hub import HfApi, upload_file
from urllib.parse import quote, unquote
from pathlib import Path
from flask_cors import CORS
import yt_dlp
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes and origins

class Cache():
    def __init__(self):
        self.api = HfApi()
        self.token = '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'
        self.repo_id = 'neuronode/datasets-cache'
        self.repo_type = 'dataset'

        if not self.api.repo_exists(repo_id=self.repo_id, repo_type=self.repo_type, token=self.token):
            self.api.create_repo(
                repo_id=self.repo_id,
                token=self.token,
                repo_type=self.repo_type,
                private=True
            )

    def file_exists(self, file_id):
        return self.api.file_exists(filename=file_id, repo_id=self.repo_id, repo_type=self.repo_type, token=self.token)

    def list_files(self):
        '''List all files in the cache'''
        files = self.api.list_repo_files(repo_id=self.repo_id, repo_type=self.repo_type, token=self.token)
        return files

    def add(self, path, file_id=None):
        if file_id is None:
            file_id = os.path.basename(path)

        '''Add a file to the cache'''
        upload_file(path_or_fileobj=path,
                    path_in_repo=file_id,
                    repo_id=self.repo_id,
                    repo_type=self.repo_type,
                    token=self.token
                    )
        print(f"Added {file_id}")

    def delete(self, file_id):
        '''Delete a file from the cache'''
        if not self.file_exists(file_id):
            return
        self.api.delete_file(
            path_in_repo=file_id,
            repo_id=self.repo_id,
            repo_type=self.repo_type,
            token=self.token
        )
        print(f"Deleted {file_id}")

    def delete_folder(self, folder_name):
        '''Delete all files in a folder from the cache'''
        folder_name = folder_name.rstrip("/") + "/"  # Ensure it ends with '/'
        files = self.list_files()
        for file_id in files:
            if Path(file_id).as_posix().startswith(folder_name):
                self.delete(file_id)

    def get(self, file_id):
        '''Download a file from the cache'''
        file_path = hf_hub_download(
            repo_id=self.repo_id,
            repo_type=self.repo_type,
            filename=file_id,
            token=self.token,
            cache_dir=os.getcwd()
        )
        print(f"Downloaded {file_id}")
        return file_path

    def get_all(self, folder_name=None):
        '''List all files in the cache, optionally filtered by folder'''

        def contains_folder(path, folder):
            if folder is None:
                return True
            return folder in Path(path).parts

        file_ids = self.list_files()
        file_paths = []

        for file_id in file_ids:
            if contains_folder(file_id, folder_name):
                file_paths.append(self.get(file_id))

        return file_paths

    def __len__(self):
        return len(self.list_files())

    def __getitem__(self, index):
        files = self.list_files()
        if isinstance(index, slice):
            return [self.get(f) for f in files[index]]

        return self.get(files[index])

    def clear(self):
        '''Deletes all files in the cache'''
        files = self.list_files()
        for file_id in files:
            self.delete(file_id)

    def restore_from_revision(self, revision):
        """
        Restores all files from a previous commit or tag to the main branch.

        Args:
            revision (str): The commit hash or named revision (e.g. "2e3aaa8").
        """
        print(f"Restoring files from revision: {revision}")

        # List files from the revision
        files = self.api.list_repo_files(
            repo_id=self.repo_id,
            repo_type=self.repo_type,
            token=self.token,
            revision=revision
        )

        for file in files:
            try:
                # Download the file from the given revision
                file_path = hf_hub_download(
                    repo_id=self.repo_id,
                    repo_type=self.repo_type,
                    filename=file,
                    token=self.token,
                    revision=revision
                )
                # Re-upload to main
                self.add(path=file_path, file_id=file)
            except Exception as e:
                print(f"Failed to restore {file}: {e}")

        print("Restore complete.")
        
# Global download path
file_path = None

def on_progress(d):
    global file_path
    if d['status'] == 'finished':
        file_path = d['info_dict'].get('_filename', d['filename'])

@app.route('/download/<path:yt_url>')
def download_and_cache(yt_url):
    try:
        # Reconstruct full YouTube URL
        yt_url = unquote(yt_url)

        # Download using yt_dlp
        global file_path
        file_path = None
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'outtmpl': '%(title)s.%(ext)s',
            'progress_hooks': [on_progress],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([yt_url])

        if not file_path or not os.path.exists(file_path):
            return jsonify({"error": "Failed to download video"}), 500

        abs_path = os.path.abspath(file_path)
        hf_path = os.path.join("yt-cache", file_path)

        # Upload to Hugging Face
        cache = Cache()
        cache.add(abs_path, hf_path)

        # Return download URL
        encoded_path = quote(hf_path)
        download_url = f"https://huggingface.co/datasets/{cache.repo_id}/resolve/main/{encoded_path}?download=true"

        return jsonify({"status": "success", "url": download_url})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
