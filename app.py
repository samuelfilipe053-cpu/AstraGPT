
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
import requests
import sqlite3
import os

load_dotenv()

app = Flask(__name__)

API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "inclusionai/ling-3.0-flash-fin:free"
DB = "astragpt.db"


def conectar():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def iniciar():
    con = conectar()

    con.execute("""
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL
        )
    """)

    con.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            role TEXT,
            content TEXT
        )
    """)

    con.commit()
    con.close()


iniciar()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chats")
def listar_chats():
    con = conectar()
    chats = con.execute(
        "SELECT * FROM chats ORDER BY id DESC"
    ).fetchall()
    con.close()

    return jsonify([dict(c) for c in chats])


@app.route("/chat/new", methods=["POST"])
def novo_chat():
    con = conectar()

    cur = con.execute(
        "INSERT INTO chats(title) VALUES(?)",
        ("Nova conversa",)
    )

    con.commit()
    chat_id = cur.lastrowid
    con.close()

    return jsonify({"id": chat_id})


@app.route("/chat/<int:chat_id>")
def abrir_chat(chat_id):
    con = conectar()

    mensagens = con.execute(
        "SELECT role,content FROM messages "
        "WHERE chat_id=? ORDER BY id",
        (chat_id,)
    ).fetchall()

    con.close()

    return jsonify([dict(m) for m in mensagens])


@app.route("/chat/<int:chat_id>/message", methods=["POST"])
def mensagem(chat_id):
    data = request.get_json()
    texto = data.get("message", "").strip()

    if not texto:
        return jsonify({"error": "Mensagem vazia."}), 400

    con = conectar()

    con.execute(
        "INSERT INTO messages(chat_id,role,content) VALUES(?,?,?)",
        (chat_id, "user", texto)
    )

    quantidade = con.execute(
        "SELECT COUNT(*) FROM messages WHERE chat_id=?",
        (chat_id,)
    ).fetchone()[0]

    if quantidade == 1:
        titulo = " ".join(texto.split()[:6])
        if len(texto.split()) > 6:
            titulo += "..."

        con.execute(
            "UPDATE chats SET title=? WHERE id=?",
            (titulo, chat_id)
        )

    historico = con.execute(
        "SELECT role,content FROM messages "
        "WHERE chat_id=? ORDER BY id",
        (chat_id,)
    ).fetchall()

    con.commit()
    con.close()

    mensagens = [{
        "role": "system",
        "content": (
            "Tu és a AstraGPT. "
            "Responde em português. "
            "Responde normalmente sem pesquisar. "
            "Só pesquisa na Web quando o utilizador pedir "
            "explicitamente."
        )
    }]

    for m in historico:
        mensagens.append({
            "role": m["role"],
            "content": m["content"]
        })

    palavras = [
        "pesquisa",
        "pesquisar",
        "procura na web",
        "procura na internet",
        "pesquisa na web",
        "pesquisa na internet"
    ]

    pesquisar = any(
        palavra in texto.lower()
        for palavra in palavras
    )

    payload = {
        "model": MODEL,
        "messages": mensagens
    }

    if pesquisar:
        payload["tools"] = [
            {"type": "openrouter:web_search"}
        ]

    try:
        resposta = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=90
        )

        dados = resposta.json()

        if resposta.status_code != 200:
            return jsonify({
                "error": dados.get("error", {}).get(
                    "message", "Erro na API."
                )
            }), 500

        resposta_ia = dados["choices"][0]["message"]["content"]

        con = conectar()

        con.execute(
            "INSERT INTO messages(chat_id,role,content) VALUES(?,?,?)",
            (chat_id, "assistant", resposta_ia)
        )

        con.commit()
        con.close()

        return jsonify({"answer": resposta_ia})

    except Exception as erro:
        return jsonify({"error": str(erro)}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)

