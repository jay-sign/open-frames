from flask import Flask, jsonify
from kaggle.api.kaggle_api_extended import KaggleApi
import os

app = Flask(__name__)

# Home route
@app.route('/')
def home():
    return '✅ Flask backend is running on Render.'

# Dynamic Kaggle dataset file listing
@app.route('/list-files/<owner>/<dataset>')
def list_kaggle_files(owner, dataset):
    try:
        # Authenticate using env vars
        api = KaggleApi()
        api.authenticate()

        # Build full dataset identifier
        dataset_path = f"{owner}/{dataset}"

        # Fetch file list
        files = api.dataset_list_files(dataset_path).files
        file_names = [f.name for f in files]

        return jsonify({
            "dataset": dataset_path,
            "file_count": len(file_names),
            "files": file_names
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 400

if __name__ == '__main__':

    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
