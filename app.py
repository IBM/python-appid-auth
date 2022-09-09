from flask import redirect

from auth import AppIDAuthProvider

auth = AppIDAuthProvider()
flask = auth.flask

@flask.route("/")
def index():
    return redirect("/auth_route")

@flask.route("/auth_route")
@auth.check
def auth_route():
    return "This route requires authentication and authorization - Powered by IBM Cloud App ID!"

@flask.route("/noauth_route")
def noauth_route():
    return "This route is open to all!"

if __name__ == "__main__":
    flask.run(host="0.0.0.0")
