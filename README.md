# Add authentication and authorization to a Python Flask web application
### - Secure an app with IBM Cloud App ID and deploy to IBM Cloud Code Engine serverless platform

This repository is associated with [this code pattern overview page](https://developer.ibm.com/patterns/add-authentication-and-authorization-to-a-python-flask-web-application). In this code pattern, you use the [IBM Cloud App ID service](https://www.ibm.com/cloud/app-id) to add authentication and authorization to a Python Flask application, protecting it from unauthorized access. You then deploy the app to [IBM Cloud Code Engine](https://www.ibm.com/cloud/code-engine), a fully managed serverless platform for containerized workloads.

Although this application is written in [Python Flask framework](https://flask.palletsprojects.com), it can be used as a reference for applications written in other programming languages as well:
  * How to use IBM Cloud App ID service for authentication and authorization
  * How to use IBM Cloud App ID service's [auth](https://cloud.ibm.com/apidocs/app-id/auth) and [management](https://cloud.ibm.com/apidocs/app-id/management) API
  * How to build and deploy a containerized application to IBM Cloud Code Engine service, including the details about how the service:
    * Pulls your application source code from GitHub
    * Builds a container image using your Dockerfile and package dependencies (requirements.txt)
    * Stores the image in your [IBM Cloud Container Registry](https://www.ibm.com/cloud/container-registry) namespace
    * Uses secrets (and configmaps) to securely handle sensitive information
    * Runs your application by fetching the container image from your Container Registry namespace
  * How to develop and test your application locally by configuring the IBM Cloud App ID service and setting appropriate environment variables on your machine

## Application deployment to IBM Cloud Code Engine

This section describes how to integrate various components shown in the following architectural diagram

![python-flask-appid-deployment-diagram](https://user-images.githubusercontent.com/65959008/192332975-9101e660-a7db-40a7-971f-75eb0482436b.png)

1. You initiate the build in your IBM Cloud Code Engine project, the Code Engine fetches files from your GitHub repository to create a container image
2. Upon successful completion of the build, Code Engine stores the container image in your IBM Cloud Container Registry namespace
3. You create the Code Engine application, the Code Engine fetches the container image from the Container Registry namespace and tries to deploy the application. This attempt fails due to missing App ID and other details
4. You configure the IBM Cloud App ID instance with the Identity Provider (IdP), redirect URI etc.
5. You set environment variables that supply App ID and other details to the Code Engine application, then Code Engine application deployment succeeds
6. You configure an authorization role in the App ID instance

*Note: The Identity Provider may not be hosted / managed by the enterprise, it can be a [Social Identity Provider](https://cloud.ibm.com/docs/appid?topic=appid-social) supported by the IBM Cloud App ID service. Also, the GitHub Repository may not be the "GitHub Enterprise".*

### Prerequisites

This code pattern requires
  * [IBM Cloud](https://cloud.ibm.com) account
  * [IBM Cloud CLI](https://www.ibm.com/cloud/cli) with [IBM Cloud Code Engine plugin](https://cloud.ibm.com/docs/cli?topic=codeengine-cli) and [IBM Cloud Container Registry plugin](https://cloud.ibm.com/docs/cli?topic=container-registry-cli-plugin-containerregcli)
  * GitHub account
  * `python3` and `pip3` if you want to run the application locally on your machine

### Before you begin

Use `ibmcloud login` CLI command to login interactively into your IBM Cloud account.

#### Create IBM Cloud IAM API key

Create a new API key using following commmand and take a note of it (`apikey`'s value in the JSON output)
```
ibmcloud iam api-key-create python-appid-apikey --output json
```
The API key is used in some of the commands below. It is also required by the Python application.

#### Create IBM Cloud Container Registry namespace

IBM Cloud Container Registry namespace is used by the IBM Cloud Code Engine service to store your application docker image.
```
ibmcloud cr namespace-add python-appid-icr-ns
```
*Notes*
* *Use -g option to set the resource group unless you want to use the default group*
* *The registry location where your namespace got created is displayed in output of the command. Following description assumes that the namespace was created in `us.icr.io`*

#### Create IBM Cloud App ID service instance

Create an IBM Cloud App ID service instance of the `graduated tier` plan, named `python-appid`. *Note: Following command uses the `us-south` location*.
```
ibmcloud resource service-instance-create python-appid appid graduated-tier us-south
```
*Note: Use -g option to set the resource group unless you want to use the default group*

### Create Code Engine project and build the container image

This section describes steps 1 and 2 in the diagram above.

Use `ibmcloud target -g <resource-group>` command to set the resource group unless you want to use the default group

Create a Code Engine project named `python-appid-proj`. The command automatically sets the newly created project as the current Code Engine context.
```
ibmcloud ce project create --name python-appid-proj
```
Create a credential named `python-appid-us-icr-cred` for the Container Registry. It is used by Code Engine to store and retrieve container images to and from the Container Registry.
```
ibmcloud ce registry create --name python-appid-us-icr-cred \
--server us.icr.io \
--username iamapikey \
--password <IBM Cloud IAM API key>
```
Create a Code Engine build configuration named `python-appid-bld`:
```
ibmcloud ce build create --name python-appid-bld \
--source https://github.com/IBM/python-appid-auth.git --commit main \
--image us.icr.io/python-appid-icr-ns/python-appid-img \
--registry-secret python-appid-us-icr-cred \
--strategy dockerfile --size small
```
Following information is supplied to the configuration:
1. `--source` option specifies that the source code should be fetched from this GitHub repository. The build fetches Python source files, the Dockerfile and the requirements.txt file. requirements.txt contains list of required Python packages. The `--commit` option specifies that code is to be pulled from the main branch.
2. `--image` option specifies that the build should store the image named `python-appid-img` in the Container Registry namespace `python-appid-icr-ns` that we previously created in the `us.icr.io` registry. The build accesses the registry using the credential named `python-appid-us-icr-cred` that you created above, which is supplied using the `--registry-secret` option.

*Note: You can optionally specify an image tag e.g. us.icr.io/python-appid-icr-ns/python-appid-img:20220817-1100. If tag is not specified, the default is latest.*

Next, run the actual build process.
```
ibmcloud ce buildrun submit --build python-appid-bld
```
This command fetches your files from the GitHub repository, creates a container image, and stores the container image in your IBM Cloud Container Registry namespace.

### Create Code Engine application

This section describes step 3 in the diagram above.

After the build is ready, you can use the container image to deploy the application. This is done by creating a Code Engine application named `python-appid-app` as follows. This command fetches the container image from the Container Registry namespace specified by the `--image` option, it uses the registry access credential specified by the `--registry-secret` option. The `--port` option specifies the port where the application listens; Flask runs on port 5000 by default:
```
ibmcloud ce application create --name python-appid-app \
--image us.icr.io/python-appid-icr-ns/python-appid-img:latest \
--registry-secret python-appid-us-icr-cred \
--port 5000 --min-scale 1
```
*Note: If `--min-scale` option (minimum number of application instances) is not specified, the default is zero. That is, the Code Engine removes all application instances if the application is not being used by anyone. That saves cost, but requires a short application startup time when scaling up from zero again. The previous command sets `--min-scale` to one to avoid this delay*

This command may take a few minutes. During that time, you can use the `ibmcloud ce application get -n python-appid-app` command in another commandline terminal to check the application status. Here is an example output of the command:
```
$ ibmcloud ce application get -n python-appid-app
For troubleshooting information visit: https://cloud.ibm.com/docs/codeengine?topic=codeengine-troubleshoot-apps.
Run 'ibmcloud ce application events -n python-appid-app' to get the system events of the application instances.
Run 'ibmcloud ce application logs -f -n python-appid-app' to follow the logs of the application instances.
OK

Name:            python-appid-app  
ID:              ...
Project Name:    python-appid-proj  
Project ID:      ...
Age:             8m2s  
...
...
Instances:     
  Name                                               Revision                Running  Status   Restarts  Age  
  python-appid-app-00001-deployment-b5f79f4bf-s29ww  python-appid-app-00001  1/3      Running  6         8m  
```
As shown in the command output, the `ibmcloud ce application create --name python-appid-app` command took more than 8 minutes and the Code Engine restarted the instance at least 6 times to try to recover out of a failure described next.

This deployment fails with an exception `raise KeyError(key)` on one of the `os.environ[]` statements in the application. This is because your Code Engine configuration is not fully complete yet. But in order to do that, you first need to configure the authentication in your App ID instance as described in the next section. You will need the Code Engine application URL during the App ID configuration, use the following command to get the URL:
```
ibmcloud ce application list
```
*Note: This command prints the application URL even if the Code Engine deployment has failed*

### Configure authentication in the App ID instance

This section describes step 4 in the diagram above.

Use [App ID documentation](https://cloud.ibm.com/docs/appid) to setup the App ID instance named `python-appid` that you created earlier:

1. This Python Flask web application redirects users to the App ID instance for authentication. So configure one of several identity providers supported by the App ID service, refer to [this documentation page](https://cloud.ibm.com/docs/appid?topic=appid-managing-idp).
2. After the App ID service authenticates a user using the identity provider, it redirects the user back to the web application using a specific route called the `redirect URI`. You need to pre-registered your application's redirect URI with the App ID instance. Append `/afterauth` to the Code Engine application URL that you noted down in the previous step and register the string with your App ID instance as described in [this documentation page](https://cloud.ibm.com/docs/appid?topic=appid-managing-idp#add-redirect-uri). Here is an example redirect URI: `https://python-appid-app.rygjo8wa2xn.us-south.codeengine.appdomain.cloud/afterauth`.
3. Create an application named `python-appid-app` of type `Regular web application` containing a scope named `view`. Take a note of its `clientId`, `secret` and `oAuthServerUrl` attributes, you will use those to link this `python-appid-app` "App ID application" with the `python-appid-app` "Code Engine application" that you created in the previous section. Next section describes how to establish this linkage.

### Set environment variables that supply App ID and other details to the Code Engine application 

This section describes step 5 in the diagram above.

The Python application deployed to the Code Engine service requires App ID's `clientId` and `secret` which is sensitive data! So first create a Code Engine secret to store those values, as well as other sensitive information that the application requires - the session secret key and the IBM Cloud API key:
```
ibmcloud ce secret create --name python-appid-app-secret \
--from-literal "APPID_CLIENT_ID=<clientId string>" \
--from-literal "APPID_CLIENT_SECRET=<secret string>" \
--from-literal "SESSION_SECRET_KEY=some random string" \
--from-literal "IBM_CLOUD_APIKEY=<IAM API key string>"
```
Next, you provide the secret to the Code Engine application using the `--env-from-secret` option. Additionally, the Python application requires the redirect URI too because it needs to send the redirect URI to the App ID service during OIDC protocol exchanges. The application also requires value of the `oAuthServerUrl` attribute of the App ID application that you created in the previous section. Following command uses the `--env` option to supply redirect URI and OAuth server details:
```
ibmcloud ce application update --name python-appid-app \
--env-from-secret python-appid-app-secret \
--env "APPID_REDIRECT_URI=<redirect URI string>" \
--env "APPID_OAUTH_SERVER_URL=<oAuthServerUrl string>"
```
Now you have completed configuration of the Code Engine application. The Code Engine will automatically create a new revision, and the deployment will be successful. Run the application URL in your browser. You will be redirected to the identity provider that you have configured in the App ID service, and after you login successfully, you will be redirected back to the application.

Yay! ... but ...

... the application will display the message "Unauthorized!" This is expected, because you have not configured "authorization" in your App ID instance yet! Next section describes how to do that by creating and assigning App ID roles.

### Configure authorization role in the App ID instance

This section describes step 6 in the diagram above.

In a previous step, you created an App ID application named `python-appid-app` that has a scope named `view`. App ID service lets you define a role that lists one or more scopes in one or more applications that the role is authorized for. Then you assign one or more roles to a user.

Refer to [App ID documentation](https://cloud.ibm.com/docs/appid?topic=appid-access-control) to create and assign a role:
1. Create a role named `user` containing the scope `python-appid-app/view`
2. Assign the `user` role to your own user profile

Now refresh the browser where your application is running or copy-paste the application URL in your browser or click on the "Open URL" link in the Code Engine web UI. You will be taken through a couple of redirects as before, and this time around, the application will display the message "This route requires authentication and authorization - Powered by IBM Cloud App ID!".

YAY!!!

As explained later, the AppIDAuthProvider class (defined in auth.py) - which has all of the App ID service integration / interactions logic - is designed such that you can selectively enable the auth check for specific routes. To try this, launch a separate private incongnito browser window and run the `/noauth_route` of the application. Notice that the application doesn't redirect to the identity provider this time, it just displays the message "This route is open to all!".

Note that now the application won't redirect to the identity provider even if you change the route back to `/auth_route`. This is because, as described in a subsequent section, the logic in the AppIDAuthProvider class automatically stores the access token in the user session. The application won't redirect to the identity provider until the token is valid, default validity is one hour. If you try the `/auth_route` after validity period of the access token, then the application will be redirected to the identity provider and the new access token will get stored again in the user session.

### Redeploying the Code Engine application after source code changes

You performed a number of setup steps thus far to get this application working. If you push any updates to the GitHub source code, just run following commands to redeploy the application to Code Engine.

First, login using `ibmcloud login` command. Then optionally select a non-default resource group using `ibmcloud target -g` command and select your Code Engine project using the `ibmcloud ce project select --name python-appid-proj` command.

1. If you want to specify a new tag for newly updated container image, update the build definition as follows. For example, replace <new tag> in the command below by current datetime string:
   
   *Note: Ignore this step if you don't want to change the image tag*
   ```
   ibmcloud ce build update --name python-appid-bld \
   --image us.icr.io/python-appid-icr-ns/python-appid-img:<new tag>
   ```
2. Then run the build:
   ```
   ibmcloud ce buildrun submit --build python-appid-bld
   ```
3. After the build is ready, redeploy the application using the new container image:
   ```
   ibmcloud ce application update --name python-appid-app \
   --image us.icr.io/python-appid-icr-ns/python-appid-img:<new tag>
   ```
   *Note: Of course, if you did not update the build definition in step 1 to specify an explicit tag for the new container image, then do not use the `--image` option in the command above. Just run the command `ibmcloud ce application update --name python-appid-app`*

## Running the application locally on your development machine

For developing and testing this application locally on your machine, you need to add one more redirect URI to your App ID instance, set a few environment variables and install two packages that your Python application requires:

1. Register an additional redirect URI `http://0.0.0.0:5000/afterauth` with your App ID instance as described in [this documentation page](https://cloud.ibm.com/docs/appid?topic=appid-managing-idp#add-redirect-uri)

2. Note down `clientId`, `secret` and `oAuthServerUrl` values of your `python-appid-app` "App ID application" that you created earlier. Set following environment variables:
   * Set `APPID_CLIENT_ID` environment variable to the value of the `clientId` key
   * Set `APPID_CLIENT_SECRET` environment variable to the value of the `secret` key
   * Set `APPID_OAUTH_SERVER_URL` environment variable to the value of the `oAuthServerUrl` key
   * Set `APPID_REDIRECT_URI` environment variable to "http://0.0.0.0:5000/afterauth"
   * Set `SESSION_SECRET_KEY` environment variable to "some random string"

3. Install package dependencies:
   ```
   pip3 install flask
   pip3 install requests
   ```
4. Run the application using `python3 app.py`

## Application logic

Refer to this page which describes [App ID concepts](https://cloud.ibm.com/docs/appid?topic=appid-key-concepts) to learn the basics like authentication, authorization, OAuth 2.0 and OIDC.

Following diagram shows authentication and authorization flow. It uses the OIDC protocol.

*Note: This diagram does not contain GitHub repository and IBM Cloud Container registry because those are used only during application deployment*

![python-flask-appid-runtime-diagram](https://user-images.githubusercontent.com/65959008/192333202-d0ed6b78-d232-424c-92ec-a04c561ae63f.png)

1. User types an application URL that requires auth in the browser, for example the URL https://python-appid-app.rygjo8wa2xn.us-south.codeengine.appdomain.cloud/auth_route
2. Application's backend running in the IBM Cloud Code Engine checks whether user session has a non-expired access token. (See `is_auth_active()` method in the `AppIDAuthProvider` class description below, this method gets invoked due to the `@auth.check` decorator on the route definition in app.py)
3. If the user session doesn't have access token or the token is expired, the browser is redirected to IBM Cloud App ID's `/authorization` endpoint. (See `start_auth()` method in the `AppIDAuthProvider` class, this method also gets invoked from `@auth.check` decorator's definition)
4. App ID in turn redirects the browser to the Identity Provider that you have configured in your App ID instance. User provides login credentials to authenticate with the Identity Provider
5. Upon successful user login, App ID redirects the browser to application's redirect-URI that you preregistered with your App ID instance
6. Application's backend running in the Code Engine retrieves user's access token and role(s) from the App ID. (See `after_auth()` method in the `AppIDAuthProvider` class)
7. Then the browser is redirected to the original URL that the user had typed in the step 1 above
8. Similar to step 2, application's backend running in the Code Engine checks whether user session has a non-expired access token. This time it does. It then checks whether the user session also has a role (See `user_has_a_role()` method in the `AppIDAuthProvider` class), and finally the URL works!

### AppIDAuthProvider class in auth.py

The `AppIDAuthProvider` class defined in auth.py contains all the App ID service integration / interaction logic. It uses the OIDC protocol as described here in [App ID documentation](https://cloud.ibm.com/docs/appid?topic=appid-web-apps).

1. It creates a `Flask` instance and stores it in an instance variable named `flask`:
   ```python
   self.flask = Flask(__name__)
   ```
2. Its `start_auth()` method redirects the application to App ID service's authorization endpoint. It sets appropriate query parameter values during the redirect such as `client_id` and `redirect_uri`. It also sets the query parameter `response_type` to the value `code` and the parameter `scope` to the value `openid` as shown below:
   ```python
   return redirect("{}?client_id={}&response_type=code&redirect_uri={}&scope=openid".format(authorization_endpoint, cls.CLIENT_ID, cls.REDIRECT_URI))
   ```
3. It defines the `/afterauth` route which is registered with the App ID service as the "redirect URI" as described earlier:
   ```python
   @self.flask.route("/afterauth")
   def after_auth():
   ...
   ```
   After the user is authenticated, App ID service redirects back to this application endpoint. The `after_auth()` method performs following tasks:
   - It sends the authorization code to the token endpoint to retrieve `access_token` and `id_token`
     ```python
     resp = requests.post(token_endpoint,
     ...
     ```
     It stores the `access_token` in Flask's `session` object.
   - It uses the `_get_user_info()` helper method to retrive user's ID and email from the `id_token`
     ```python
     user_email, user_id = AppIDAuthProvider._get_user_info(resp_json["id_token"])
     ```
   - It uses the `_get_user_roles()` helper method to retrieve user's roles using the user's ID
     ```python
     resp_json = AppIDAuthProvider._get_user_roles(user_id)
     ```
     It stores the roles in Flask's `session` object.
     
     *Note: If you want to add fine-grained authorization that checks whether the logged in user has particular application scope(s), then modify this logic to retrieve details about the roles. Refer to [APP ID Roles API](https://cloud.ibm.com/apidocs/app-id/management#getrole).*
   - Finally, the `/afterauth` route redirects the application to the route that had originally redirected the appication to the authorization endpoint:
     ```python
     endpoint_context = session.pop(AppIDAuthProvider.ENDPOINT_CONTEXT, None)
     return redirect(endpoint_context)
     ```
4. The `AppIDAuthProvider` class uses Flask's `session` to store user's `access_token` and roles.
   ```python
   session[AppIDAuthProvider.APPID_USER_TOKEN] = access_token
   session[AppIDAuthProvider.APPID_USER_ROLES] = resp_json["roles"]
   ```
   Before redirecting the application to the authorization endpoint, the application logic checks whether `access_token` already exists in the session and whether it is still valid (default validity of App ID tokens is 1 hour). This provides better user experience because application is not redirected to the authorization endpoint if valid `access_token` is already present in the session. Validity of `access_token` is checked using App ID service's `introspect` endpoint as described next.
5. The `is_auth_active()` method uses the `introspect` API provided by the App ID service to check whether the `access_token` stored in the session is still valid or not
   ```python
   resp = requests.post(introspect_endpoint,
                        data = {"token": token},
                        auth = HTTPBasicAuth(cls.CLIENT_ID, cls.CLIENT_SECRET))
   resp_json = resp.json()
   if "active" in resp_json and resp_json["active"]:
       return True, ""
   ...
   ```
6. The `AppIDAuthProvider` class defines the `check()` method that performs user authentication and authorization
   Following code checks whether the authentication is active / valid:
   ```python
   auth_active, err_msg = cls.is_auth_active()
   if not auth_active:
       ...
   ```
   Following code checks the authorization:
   ```python
   if not cls.user_has_a_role():
       return "Unauthorized!"
   ...
   ```
   *Note: Modify this logic if you want to add fine-grained authorization that checks whether the logged in user has specific role(s) or specific application scope(s)*
   
   The `check()` method is implicitly invoked using the "decorator" feature of the Python language as described below.

### Flask web application in app.py

The app.py file contains Flask routes. The logic in this file is very straight forward because the `AppIDAuthProvider` class in auth.py does all the auth heavy lifting as described in the previous section.

To start with, the `AppIDAuthProvider` class is imported from auth.py and an instance of the class is stored in a variable named `auth`. Also, the `flask` instance-variable of the class is stored in a variable named `flask` for improved readability of the subsequent code:
```python
from auth import AppIDAuthProvider

auth = AppIDAuthProvider()
flask = auth.flask
```
It then defines a default route using the idiomatic Flask `route` decorator:
```python
@flask.route("/")
def index():
    return redirect("/auth_route")
```
The `index()` function associated with the `/` route simply redirects to the `/auth_route` so that when you click on the Code Engine application URL, the application just works; you don't need to additionally type a route in your browser. If the `/` route is not defined, you would get 404 Not Found error when you click the Code Engine application URL.

Next, it defines the `/auth_route` using the `@flask.route("/auth_route")` decorator on the `auth_route()` function. But notice that there is one more decorator, `@auth.check`, on this function:
```python
@flask.route("/auth_route")
@auth.check
def auth_route():
    return "This route requires authentication and authorization - Powered by IBM Cloud App ID!"
```
The `@auth.check` decorator implicitely invokes the `check()` method of the `AppIDAuthProvider` class that triggers authentication and authorization flow as previously described. Accordingly, the function returns an informative message.

The application defines one more route using the `@flask.route("/noauth_route")` decorator on the `noauth_route()` function:
```python
@flask.route("/noauth_route")
def noauth_route():
    return "This route is open to all!"
```
As announced by its return value, this route is unauthenticated. This is because it doesn't have the additional `@auth.check` decorator.

Finally, the application runs the Flask instance at the default 5000 port:
```python
if __name__ == "__main__":
    flask.run(host="0.0.0.0")
```

## Cleanup

Run following commands in the IBM Cloud CLI to remove the resources that you created in this code pattern:

1. Remove the IBM Cloud Container Registry namespace:
```
ibmcloud cr namespace-rm python-appid-icr-ns
```
*Note: Use -g option to specify the resource group if you used that option when you created the namespace*

2. Delete the IBM Cloud App ID service instance:
```
ibmcloud resource service-instance-delete python-appid
```
*Note: Use -g option to specify the resource group if you used that option when you created the App ID instance*

3. Delete the IBM Cloud Code Engine project:

First use the `ibmcloud target -g <resource-group>` command to set the resource group unless you had created the project in the default group.

Then use the following command to delete the project:
```
ibmcloud ce project delete --name python-appid-proj --hard
```
*Note: If you do not specify the `--hard` option, Code Engine allows you to restore the project within a few days after the 'soft' delete*

## Summary

In this code pattern IBM Cloud App ID service was used to add authentication and authorization to a Python web application that uses the Flask framework. The code pattern also described deployment of the application to IBM Cloud Code Engine, a fully managed serverless platform for containerized applications. The IBM Cloud Code Engine service enables you to quickly deploy your application to make it available to your end users, and the IBM Cloud App ID service protects your application from unauthorized access.

## License

This code pattern is licensed under the Apache License, Version 2. Separate third-party code objects invoked within this code pattern are licensed by their respective providers pursuant to their own separate licenses. Contributions are subject to the [Developer Certificate of Origin, Version 1.1](https://developercertificate.org/) and the [Apache License, Version 2](https://www.apache.org/licenses/LICENSE-2.0.txt).

[Apache License FAQ](https://www.apache.org/foundation/license-faq.html#WhatDoesItMEAN)
