from flask import Flask, render_template, request, session, redirect, url_for
from chatbot import CompanyChatbot

app = Flask(__name__)
app.secret_key = "secret"

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

SUGGESTED_QUESTIONS = [
    "What services do you provide?",
    "Do you develop web applications?",
    "Do you develop mobile applications?",
    "Do you provide maintenance support?",
    "How can I contact your team?",
    "Do you provide custom software solutions?",
    "How much does a project cost?",
    "Do you provide support after delivery?"
]


@app.route("/")
def welcome():
    session.pop("chat_messages", None)
    return render_template("welcome.html")


@app.route("/customer", methods=["GET", "POST"])
def customer():
    if "chat_messages" not in session:
        session["chat_messages"] = []

    if request.method == "POST":
        user_message = request.form.get("message", "").strip()

        if user_message:
            chatbot = CompanyChatbot()
            bot_reply = chatbot.get_response(user_message)
            chatbot.close()

            chat_messages = session.get("chat_messages", [])
            chat_messages.append({"sender": "user", "text": user_message})
            chat_messages.append({"sender": "bot", "text": bot_reply})

            session["chat_messages"] = chat_messages
            session.modified = True

    return render_template(
        "customer.html",
        suggested_questions=SUGGESTED_QUESTIONS,
        chat_messages=session["chat_messages"]
    )


@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    error = ""

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session["admin_logged_in"] = True
            return redirect(url_for("admin"))
        else:
            error = "Invalid username or password"

    return render_template("admin_login.html", error=error)


@app.route("/admin")
def admin():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    chatbot = CompanyChatbot()
    faq_data = chatbot.get_faq_data()
    unknown_questions = chatbot.get_unknown_questions()
    chat_history = chatbot.get_chat_history()
    chatbot.close()

    return render_template(
        "admin.html",
        faq_data=faq_data,
        unknown_questions=unknown_questions,
        chat_history=chat_history
    )


@app.route("/add-faq", methods=["POST"])
def add_faq():
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    question = request.form.get("question", "").strip()
    answer = request.form.get("answer", "").strip()

    if question and answer:
        chatbot = CompanyChatbot()
        chatbot.add_faq(question, answer)
        chatbot.close()

    return redirect(url_for("admin"))


@app.route("/logout")
def logout():
    session.pop("admin_logged_in", None)
    return redirect(url_for("welcome"))


@app.route("/delete-faq/<int:faq_id>")
def delete_faq(faq_id):
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    chatbot = CompanyChatbot()
    chatbot.delete_faq(faq_id)
    chatbot.close()

    return redirect(url_for("admin"))


@app.route("/edit-faq/<int:faq_id>", methods=["GET", "POST"])
def edit_faq(faq_id):
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    chatbot = CompanyChatbot()

    if request.method == "POST":
        question = request.form.get("question", "").strip()
        answer = request.form.get("answer", "").strip()

        if question and answer:
            chatbot.update_faq(faq_id, question, answer)

        chatbot.close()
        return redirect(url_for("admin"))

    # GET
    faq = chatbot.get_faq_by_id(faq_id)
    chatbot.close()

    return render_template("edit_faq.html", faq=faq)


@app.route("/convert-unknown/<int:question_id>", methods=["GET", "POST"])
def convert_unknown(question_id):
    if not session.get("admin_logged_in"):
        return redirect(url_for("admin_login"))

    chatbot = CompanyChatbot()

    if request.method == "POST":
        answer = request.form.get("answer", "").strip()

        if answer:
            chatbot.convert_unknown_to_faq(question_id, answer)
            chatbot.close()
            return redirect(url_for("admin"))

    unknown_question = chatbot.get_unknown_question_by_id(question_id)
    chatbot.close()

    return render_template("convert_unknown.html", unknown_question=unknown_question)


if __name__ == "__main__":
    app.run(debug=True)