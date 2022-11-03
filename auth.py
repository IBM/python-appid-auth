import os
import logging
import json
import base64
import functools

from flask import Flask, redirect, request, session

import requests
from requests.auth import HTTPBasicAuth
from requests.structures import CaseInsensitiveDict

class AppIDAuthProvider:

    # App ID

    APPID_MGMT_TOKEN = ""

    CLIENT_ID = os.environ["APPID_CLIENT_ID"]
    CLIENT_SECRET = os.environ["APPID_CLIENT_SECRET"]
    REDIRECT_URI = os.environ["APPID_REDIRECT_URI"]

    OAUTH_SERVER_URL = os.environ["APPID_OAUTH_SERVER_URL"]
    MANAGEMENT_URL = OAUTH_SERVER_URL.replace("oauth", "management")

    # IAM

    IAM_TOKEN_ENDPOINT = "https://iam.cloud.ibm.com/identity/token"

    # Session

    APPID_USER_TOKEN = "APPID_USER_TOKEN"
    APPID_USER_ROLES = "APPID_USER_ROLES"
    AUTH_ERRMSG = "AUTH_ERRMSG"
    ENDPOINT_CONTEXT = "ENDPOINT_CONTEXT"

    def __init__(self):

        logging.basicConfig(level = logging.INFO)

        self.flask = Flask(__name__)
        self.flask.secret_key = os.environ["SESSION_SECRET_KEY"]

        @self.flask.route("/afterauth")
        def after_auth():
            # This route is pre-registered with the App ID service instance as
            # the 'redirect' URI, so that it can redirect the flow back into
            # the application after successful authentication
            err_msg = ""
            if "code" in request.args:
                code = request.args.get("code")
                # Send the authorization code to the token endpoint to retrieve access_token and id_token
                token_endpoint = AppIDAuthProvider.OAUTH_SERVER_URL + "/token"
                resp = requests.post(token_endpoint,
                                     data = {"client_id": AppIDAuthProvider.CLIENT_ID,
                                             "grant_type": "authorization_code",
                                             "redirect_uri": AppIDAuthProvider.REDIRECT_URI,
                                             "code": code},
                                     auth = HTTPBasicAuth(AppIDAuthProvider.CLIENT_ID, AppIDAuthProvider.CLIENT_SECRET))
                resp_json = resp.json()
                if "error_description" in resp_json:
                    err_msg = "Could not retrieve user tokens, {}".format(resp_json["error_description"])
                elif "id_token" in resp_json and "access_token" in resp_json:
                    access_token = resp_json["access_token"]
                    user_email, user_id = AppIDAuthProvider._get_user_info(resp_json["id_token"])
                    resp_json = AppIDAuthProvider._get_user_roles(user_id)
                    if "roles" in resp_json:
                        session[AppIDAuthProvider.APPID_USER_TOKEN] = access_token
                        session[AppIDAuthProvider.APPID_USER_ROLES] = resp_json["roles"]
                        logging.info(" User {} logged in".format(user_email))
                    else:
                        err_msg = "Could not retrieve user roles"
                        if "error_description" in resp_json:
                            err_msg = err_msg + ", " + resp_json["error_description"]
                else:
                    err_msg = "Did not receive 'id_token' and / or 'access_token'"
            else:
                err_msg = "Did not receive 'code' from the authorization server"
            if err_msg:
                logging.error(err_msg)
                session[AppIDAuthProvider.AUTH_ERRMSG] = err_msg
            endpoint_context = session.pop(AppIDAuthProvider.ENDPOINT_CONTEXT, None)
            return redirect(endpoint_context)

    @classmethod
    def check(cls, func):
        @functools.wraps(func)
        def wrapper_check(*args, **kwargs):
            auth_active, err_msg = cls._is_auth_active()
            if not auth_active:
                if err_msg:
                    return "Internal error: " + err_msg
                else:
                    return cls.start_auth()
            else:
                if not cls._user_has_a_role():
                    return "Unauthorized!"
                else:
                    return func(*args, **kwargs)
        return wrapper_check

    @classmethod
    def _is_auth_active(cls):
        if cls.AUTH_ERRMSG in session:
            return False, session.pop(cls.AUTH_ERRMSG)
        elif cls.APPID_USER_TOKEN in session:
            token = session[cls.APPID_USER_TOKEN]
            introspect_endpoint = cls.OAUTH_SERVER_URL + "/introspect"
            resp = requests.post(introspect_endpoint,
                                 data = {"token": token},
                                 auth = HTTPBasicAuth(cls.CLIENT_ID, cls.CLIENT_SECRET))
            resp_json = resp.json()
            if "active" in resp_json and resp_json["active"]:
                return True, ""
            else:
                session.pop(cls.APPID_USER_TOKEN, None)
                session.pop(cls.APPID_USER_ROLES, None)
                err_msg = ""
                if "error_description" in resp_json:
                    err_msg = "Could not introspect user token, {}".format(resp_json["error_description"])
                    logging.error(err_msg)
                return False, err_msg
        else:
            return False, ""

    @classmethod
    def start_auth(cls):
        # This method redirects the application to App ID service's authorization endpoint. The App ID service
        # in turn uses its pre-configured identity provider for user authentication
        if cls.ENDPOINT_CONTEXT not in session:
            session[cls.ENDPOINT_CONTEXT] = request.path
        authorization_endpoint = cls.OAUTH_SERVER_URL + "/authorization"
        return redirect("{}?client_id={}&response_type=code&redirect_uri={}&scope=openid".format(authorization_endpoint, cls.CLIENT_ID, cls.REDIRECT_URI))

    # This method and the next method use base64 decoding to retrive user's ID and email
    # stored inside the id_token
    @staticmethod
    def _get_user_info(id_token):
        decoded_id_token = AppIDAuthProvider._base64_decode(id_token.split('.')[1])
        id_token_details = json.loads(decoded_id_token)
        return id_token_details["email"], id_token_details["sub"]

    @staticmethod
    def _base64_decode(data):
        data += '=' * (4 - len(data) % 4) # pad the data as needed
        return base64.b64decode(data).decode('utf-8')

    @classmethod
    def _get_user_roles(cls, user_id):
        resp = cls._exec_user_roles_req(user_id)
        if resp.status_code == 403:
            return { "error_description": "Forbidden" }
        if resp.status_code == 401:
            # App ID management access token has expired, retrieve it again
            err_msg = cls._get_appid_mgmt_access_token()
            if err_msg:
                return { "error_description": err_msg }
            # Try the previous call again now that the App ID management
            # access token has been refreshed
            resp = cls._exec_user_roles_req(user_id)
            if resp.status_code == 403:
                return { "error_description": "Forbidden" }
        resp_json = resp.json()
        if "roles" in resp_json:
            roles = []
            for role in resp_json["roles"]:
                roles.append(role["name"])
            return { "roles": roles }
        elif "Error" in resp_json and "Status" in resp_json["Error"]:
            # resp_json contains "Error" if the error is emitted by IAM
            return { "error_description": resp_json["Error"]["Status"] }
        elif "errorCode" in resp_json:
            # resp_json contains "errorCode" if the error is emitted by App ID
            return { "error_description": resp_json["errorCode"] }

    @classmethod
    def _exec_user_roles_req(cls, user_id):
        user_roles_endpoint = cls.MANAGEMENT_URL + "/users/{}/roles".format(user_id)
        headers = CaseInsensitiveDict()
        headers["Authorization"] = "Bearer {}".format(cls.APPID_MGMT_TOKEN)
        return requests.get(user_roles_endpoint, headers=headers)

    @classmethod
    def _get_appid_mgmt_access_token(cls):
        resp = requests.post(cls.IAM_TOKEN_ENDPOINT,
                             data = {"grant_type": "urn:ibm:params:oauth:grant-type:apikey",
                                     "apikey": os.environ["IBM_CLOUD_APIKEY"]})
        resp_json = resp.json()
        if "access_token" in resp_json:
            cls.APPID_MGMT_TOKEN = resp_json["access_token"]
            return ""
        else:
            err_msg = "could not retrieve App ID management access token"
            if "errorCode" in resp_json:
                err_msg = err_msg + ", " + resp_json["errorCode"]
            return err_msg

    @classmethod
    def _user_has_a_role(cls):
        if cls.APPID_USER_ROLES in session and session[cls.APPID_USER_ROLES]:
            return True
        else:
            session.pop(cls.APPID_USER_TOKEN, None)
            session.pop(cls.APPID_USER_ROLES, None)
            return False
