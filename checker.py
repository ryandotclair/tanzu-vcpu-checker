#! /usr/bin/python
import os
import argparse
import requests
import logging
import pandas as pd
from datetime import datetime

subscription = os.environ['AZURE_SUBSCRIPTION']
directory_id = os.environ['AZURE_TENANTID']
app_id = os.environ['AZURE_APP_ID']
app_value_id = os.environ['AZURE_APP_VALUEID']

Parser = argparse.ArgumentParser(prog='checker.py', description='Simple program to check active vCPUs currently being consumed by Azure Spring Apps Enterprise. Developed by Ryan Clair')
subparsers = Parser.add_subparsers(dest='verb')
console_parser = subparsers.add_parser('console', help="Formatted for the console.")
csv_parser = subparsers.add_parser('csv', help="Formatted for csv.")
csv_parser.add_argument('-f', '--file', action="store_true", default=False, help="Optionally use this to write the results to a file called vcpu-report.csv")
args = Parser.parse_args()

def azure_auth():
    # This function returns the bearer token that's used in follow up API calls
    try:
        url = f"https://login.microsoftonline.com/{directory_id}/oauth2/token"

        payload = f"grant_type=client_credentials&client_id={app_id}&client_secret={app_value_id}&resource=https%3A%2F%2Fmanagement.azure.com%2F"

        headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
        }

        response = requests.request("POST", url, headers=headers, data=payload)
        logging.debug(f"response from azure_auth function: {response}")

        bearer_token = response.json()["access_token"]

        return bearer_token

    except requests.exceptions.RequestException as e:
        error_message = f"Error occurred: {e}"
        logging.info(error_message)
        return "Error. Issue authenticating with Azure API"

def console_report():
    # This function generates a report, written to the console

    # Grab all RG's in Subscription
    rg_url = f"https://management.azure.com/subscriptions/{subscription}/resourcegroups?api-version=2021-04-01"
    response = requests.get(rg_url, headers=headers)
    rg_list = response.json()["value"]
    rgs = []
    rTotalCPU = 0
    TotalCPU = 0
    print("RGs Discovered...")
    for r in rg_list:
        rgs.append(r["name"])
        print(f'  {r["name"]}')

    print(" ")
    for rg in rgs:
        rTotalCPU = 0
        services_url = f"https://management.azure.com/subscriptions/{subscription}/resourceGroups/{rg}/providers/Microsoft.AppPlatform/Spring?api-version=2023-05-01-preview"
        response = requests.get(services_url, headers=headers)
        services_list = response.json()["value"]
        services = []
        if len(services_list) > 0:
            print(f"ASA-E Instances Discovered in RG {rg}...")
        else:
            print(f"None found in RG {rg}")
            continue
        # Walk through all services
        for s in services_list:
            # Check if Enterprise Tier, and it's running
            if s["sku"]["tier"] == "Enterprise" and s["properties"]["powerState"] == "Running":
                # If so, add to the list
                services.append(s["name"])
                print(f"  {s['name']}")
        # Walk through each ASA-E Instance and grab app list
        for service in services:
            try:
                apps_url = f"https://management.azure.com/subscriptions/{subscription}/resourceGroups/{rg}/providers/Microsoft.AppPlatform/Spring/{service}/apps?api-version=2023-05-01-preview"
                response = requests.get(apps_url, headers=headers)
                apps_list = response.json()["value"]
                apps = []
                for a in apps_list:
                    # Check for only for properly provisioned apps on ASA-E apps
                    if a["properties"]["provisioningState"] == "Succeeded":
                        apps.append(a["name"])
            except Exception as e:
                # In event of an error, note it
                print(f"!!! Error: RG {rg} | Service {service} | Error {e}")
                continue
            sTotalCPU = 0
            print(" ")
            print(f"Service {service}...")
            # For each app in the service, grab the active deployment's infra needs
            for app in apps:
                deployments_url = f"https://management.azure.com/subscriptions/{subscription}/resourceGroups/{rg}/providers/Microsoft.AppPlatform/Spring/{service}/apps/{app}/deployments?api-version=2023-05-01-preview"
                try:
                    response = requests.get(deployments_url, headers=headers,timeout=20)
                except requests.exceptions.Timeout:
                    # Assume after 20 seconds it's "hung", note the failure and skip
                    print(f"!!RG {rg} | App: {app} | Active deployment: {deployment['name']} | TIMEOUT ERROR")
                    continue
                deployments = response.json()["value"]
                for deployment in deployments:
                    # Grab the active deployment's infra needs IF the app is running.
                    if deployment["properties"]["active"] and deployment["properties"]["status"] == "Running":
                        cpu = deployment["properties"]["deploymentSettings"]["resourceRequests"]["cpu"]
                        capacity = deployment["sku"]["capacity"]

                        # Multiply the vCPU (scale up) by the number of app instances (scale out) to get total vCPUs
                        total = int(cpu) * capacity
                        sTotalCPU += total
                        active_deployment_name = deployment["name"]
                        print(f"  RG {rg} | App: {app} | Active deployment: {active_deployment_name} | vCPUs {total}")
            print(f"Service {service} | Total vCPUs {sTotalCPU}")
            print(" ")
            rTotalCPU += sTotalCPU
        print(f"RG {rg} | Total CPUs {rTotalCPU}")
        print(" ")
        TotalCPU += rTotalCPU
    print(" ")
    print(f"Subscription {subscription} | Total vCPUs Found {TotalCPU}")

def csv_format():
    # This function print out either to console or to straight to file a report using Comma-Separated Values format with this column header:
    # Timestamp, Resource Group, Instance Name, App Name, Active Deployment, Total vCPUs

    # Grab all RG's in Subscription
    rg_url = f"https://management.azure.com/subscriptions/{subscription}/resourcegroups?api-version=2021-04-01"
    response = requests.get(rg_url, headers=headers)
    rg_list = response.json()["value"]
    rgs = []
    rows = []
    rTotalCPU = 0
    TotalCPU = 0
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    # Cycle through the json response, pulling out all the RG names
    for r in rg_list:
        rgs.append(r["name"])

    if not args.file:
        # If this isn't straight to file, print headers to screen
        print("Timestamp, Resource Group, Instance Name, App Name, Active Deployment, Total vCPUs")

    for rg in rgs:
        # For each RG, look for ASA-E instances
        rTotalCPU = 0
        services_url = f"https://management.azure.com/subscriptions/{subscription}/resourceGroups/{rg}/providers/Microsoft.AppPlatform/Spring?api-version=2023-05-01-preview"
        response = requests.get(services_url, headers=headers)
        services_list = response.json()["value"]
        services = []
        if len(services_list) == 0:
            # Skip RG if there are no ASA-E instances in it.
            continue

        # If there are ASA-E instances, walk through all instances and find the powered on ones.
        for s in services_list:
            # Check if it's Enterprise Tier and is powered on
            if s["sku"]["tier"] == "Enterprise" and s["properties"]["powerState"] == "Running":
                # If so, add to the list
                services.append(s["name"])

        # Walk through each powered on ASA-E Instance and grab app names.
        for service in services:
            try:
                apps_url = f"https://management.azure.com/subscriptions/{subscription}/resourceGroups/{rg}/providers/Microsoft.AppPlatform/Spring/{service}/apps?api-version=2023-05-01-preview"
                response = requests.get(apps_url, headers=headers)
                apps_list = response.json()["value"]
                apps = []
                for a in apps_list:
                    # Check for only for properly provisioned apps on ASA-E apps
                    if a["properties"]["provisioningState"] == "Succeeded":
                        apps.append(a["name"])
            except Exception as e:
                # In event of an error, note it
                print(f"!!! Error: RG {rg} | Service {service} | Error {e}")
                continue
            sTotalCPU = 0
            # For each powered on app in the service, look at it's deployments.
            for app in apps:
                deployments_url = f"https://management.azure.com/subscriptions/{subscription}/resourceGroups/{rg}/providers/Microsoft.AppPlatform/Spring/{service}/apps/{app}/deployments?api-version=2023-05-01-preview"
                try:
                    response = requests.get(deployments_url, headers=headers,timeout=20)
                except requests.exceptions.Timeout:
                    # Assuming 20 seconds has passed and it's still hanging, assume an issue, note the failure and skip
                    print(f"{rg}, {service}, {app}, {deployment['name']}, TIMEOUT ERROR")
                    continue
                deployments = response.json()["value"]

                # Walk through each deployment in the app...
                for deployment in deployments:
                    # And grab the active deployment's infra needs if the app is powered on and running.
                    if deployment["properties"]["active"] and deployment["properties"]["status"] == "Running":
                        cpu = deployment["properties"]["deploymentSettings"]["resourceRequests"]["cpu"]
                        capacity = deployment["sku"]["capacity"]

                        # Multiply the vCPU (scale up) by the number of app instances (scale out) to get total vCPUs
                        total = int(cpu) * capacity
                        # Add the vCPU to the Service's total
                        sTotalCPU += total
                        active_deployment_name = deployment["name"]

                        # If this is a csv -f situation, store this in the list
                        if args.file:
                            rows.append([now,rg,service,app,active_deployment_name,total])
                        else:
                            # Otherwise print it to console
                            print(f"{now}, {rg}, {service}, {app}, {active_deployment_name}, {total}")
            # Add the Service's total to the RG's total
            rTotalCPU += sTotalCPU
        # Add RG's total to the Subscription's Total
        TotalCPU += rTotalCPU
    print(" ")

    # If this is a csv -f situation, write to disk
    if args.file:
        df = pd.DataFrame(data=rows, columns = ['Timestamp', 'Resource Group', 'Service Name', 'App Name', 'Active Deployment Name', 'Total vCPUs'])

        # If the file already exists, append without headers, otherwise with headers
        if os.path.isfile('vcpu_report.csv'):
            df.to_csv('vcpu_report.csv',mode='a', index=False,header=False)
        else:
            df.to_csv('vcpu_report.csv',mode='a', index=False,header=True)
        print("Done")
    # If it's not to disk, then print totals to screen
    else:
        print(f"Subscription {subscription} | Total vCPUs Found {TotalCPU}")

# Grab Authorization Token (to be used in the functions below)
azure_token = azure_auth()
headers = {
    "Authorization": f"Bearer {azure_token}"
}

if args.verb == "console":
    console_report()
elif args.verb == "csv":
    csv_format()
else:
    Parser.print_help()
