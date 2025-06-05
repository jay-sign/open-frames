from flask import Flask, jsonify
app = Flask(__name__)

# Example static file list (replace with your dynamic code)
files = [
    "file1.zip",
    "file2.csv",
    "images/img1.png",
    "videos/video1.mp4"
]

@app.route('/files')
def list_files():
    return jsonify(files)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
