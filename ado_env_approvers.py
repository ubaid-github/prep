import requests
from requests.auth import HTTPBasicAuth
import json
from decouple import config
import sys

class AdoEnvApprovers:
    """
    This class represents an object to manage Azure DevOps (ADO) environment approvers.
    
    Attributes:
        personal_access_token (str): The personal access token (PAT) for authenticating with ADO.
        account (str): The name of the ADO account to use.
        pipeline_env (str): The name of the ADO pipeline environment to manage.
        
    Methods:
        __init__(personal_access_token: str, account: str, pipeline_env: str):
            Initializes a new instance of the AdoEnvApprovers class.
            
        __get_account_id():
            Helper method to get the account ID for the specified ADO account.
            
        __get_pipeline_env_id(project: str):
            Helper method to get the pipeline environment ID for the specified ADO project.
        
        add_approvers_to_env(project):
            Adds approvers to the specified ADO pipeline environment.
    """
    
    ADO_APPROVAL_GUID = "8C6F20A7-A545-4486-9777-F762FAFE0D4D"
    MIN_REQUIRED_APPROVERS = 1
    ADO_PERSONAL_ACCESS_TOKEN = config("ADO_PERSONAL_ACCESS_TOKEN")
    ADO_API_VERSION = "7.0"
    
    def __init__(self, personal_access_token: str, account: str, pipeline_env: str):
        """
        Initializes a new instance of the AdoEnvApprovers class with the specified parameters.

        Args:
            personal_access_token (str): The personal access token (PAT) for authenticating with ADO.
            account (str): The name of the ADO account to use.
            pipeline_env (str): The name of the ADO pipeline environment to manage.
        """
        
        self.organization_url = "https://dev.azure.com/ubaidce"
        self.credentials = HTTPBasicAuth("", self.__get_personal_access_token())
        self.account = account
        self.pipeline_env = pipeline_env
        self.headers = {
            "Content-Type": "application/json"
        }
               
    def add_approvers_to_env(self, project):
        """
            Adds the current user as an approver to the specified pipeline environment in the given project.
            The method sends a POST request to the Azure DevOps REST API to add the current user as an approver to the specified pipeline environment.
            The `project` argument is used to construct the API URL. The method retrieves the account ID and pipeline environment ID from the instance properties
            and constructs a JSON payload with the necessary settings to create the approval. The method then sends the API request with the payload using
            the `requests` library, and raises an HTTP error if the response status code indicates failure. Finally, the method prints a success message and
            returns the HTTP status code of the response.

            Args:
                self: An instance of the `PipelineClient` class.
                project (str): The name or ID of the project containing the pipeline.

            Returns:
                int: The HTTP status code of the API response.

            Raises:
                requests.exceptions.HTTPError: If the API request fails.

        """
    
        url = f'{self.organization_url}/{project}/_apis/pipelines/checks/configurations?api-version={self.ADO_API_VERSION}-preview.1'
        account_id = self.__get_account_id()
        pipeline_env_id = self.__get_pipeline_env_id(project)
        if account_id in self.__check_approver_presence(project):
            print(f"Account ({self.account} with {account_id}) already present in the approvers list for {self.pipeline_env} in {project}, skipping....")
            sys.exit(1)
        body = {
                "type": {
                    "id": self.ADO_APPROVAL_GUID,
                    "name": "Approval"
                },
                "settings": {
                    "approvers": [
                    {
                        "displayName": self.account,
                        "id": account_id,
                        "uniqueName": self.account
                    }
                    ],
                    "executionOrder": 1,
                    "instructions": "",
                    "blockedApprovers": [],
                    "minRequiredApprovers": self.MIN_REQUIRED_APPROVERS,
                    "requesterCannotBeApprover": False
                },
                "resource": {
                    "type": "environment",
                    "id": pipeline_env_id,
                    "name": self.pipeline_env
                },
                "timeout": 43200
        }
        response = requests.post(url=url, headers=self.headers, data=json.dumps(body), auth=self.credentials)
        response.raise_for_status()
        print(f"Successfully added {self.account} to the {self.pipeline_env} of {project}")
        return response.status_code
    
    def __get_personal_access_token(self):
        """        
        Returns:
            str: The PAT token to be used for API Auth.
        """
        
        return self.ADO_PERSONAL_ACCESS_TOKEN
    
    def __check_approver_presence(self, project: str) -> list[str]:
        """
            Checks if there are any approvers assigned to the pipeline checks for the specified project and environment.
            
            Args:
                project: A string representing the name of the project to check.
            
            Returns:
                A list of strings representing the IDs of the approvers assigned to the pipeline checks.
                If there are no approvers, an empty list is returned.
        """
        
        url = f'{self.organization_url}/{project}/_environments/{self.__get_pipeline_env_id(project)}/checks?__rt=fps&api-version={self.ADO_API_VERSION}'
        response = requests.get(url=url, headers=self.headers, auth=self.credentials)
        approvers_list = []

        try:
            check_data_list = response.json()["fps"]["dataProviders"]['data']['ms.vss-pipelinechecks.checks-data-provider']["checkConfigurationDataList"]
        except KeyError as e:
            print(f"Error: {e}")
            check_data_list = []
        else:
            for i in check_data_list:
                try:
                    approvers = i['checkConfiguration']['settings']['approvers']
                except KeyError as e:
                    print(f"Error: {e}")
                    approvers = []
                    
                for j in approvers:
                    try:
                        approvers_list.append(j["id"])
                    except KeyError as e:
                        print(f"Error: {e}")
                
        finally:
            return approvers_list
        
    def __get_account_id(self):
        """
        Gets the account ID for the specified ADO account.
        
        Returns:
            str: The ID of the specified ADO account.
        """
        
        url = f"{self.organization_url}/_apis/IdentityPicker/Identities?api-version={self.ADO_API_VERSION}-preview.1"
        body = {
            "query": self.account,
            "identityTypes": ["user", "group"],
            "operationScopes": ["ims", "source"]
        }
        response = requests.post(url=url, headers=self.headers, data=json.dumps(body), auth=self.credentials)
        response.raise_for_status()
        if response.status_code != 200:
            print("Verify your PAT token is correct")
            sys.exit(1)
        results = response.json()['results'][0].get('identities', [])
        if len(results) == 0:
            raise ValueError(f"No results found for account '{self.account}'")
        elif len(results) > 1:
            raise ValueError(f"Multiple results found for account '{self.account}'")
        account_id = response.json()['results'][0]['identities'][0]['originId']
        return account_id
        
    def __get_pipeline_env_id(self, project: str):
        """
        Helper method to get the pipeline environment ID for the specified ADO project.
        
        Args:
            project (str): The name of the ADO project to use.
            
        Returns:
            str: The ID of the specified ADO pipeline environment.
        """
        
        url = f"{self.organization_url}/{project}/_apis/distributedtask/environments?name={self.pipeline_env}&api-version={self.ADO_API_VERSION}"
        response = requests.get(url=url, headers=self.headers, auth=self.credentials)
        response.raise_for_status()
        if response.json()['count'] == 0:
            raise ValueError(f"No environment found with name {self.pipeline_env}")
        pipeline_env_id = response.json()["value"][0]["id"]
        return pipeline_env_id
      
    
        
#debug
if __name__ == '__main__':
    ado_instance = AdoEnvApprovers("dummy_pat", "ubaidce@gmail.com", "QA1")
    ado_instance.add_approvers_to_env("ado-env-approver-code")
    

