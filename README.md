# Overview

This tool checks an Azure's subscription for any Azure Spring App Enterprise instances (across all Resource Groups) and counts all powered on app's vCPUs. This requires Read access to your subscription.

# Installation Steps

## Grant this Script Read-Only Permissions to your Azure Subscription
Create a registered app (`tanzu-vcpu-checker`) with read-only access to your subscription.


```
export AZURE_SUBSCRIPTION=<Your Azure Subscription ID>
export AZURE_TENANTID=<Your Tenant/Directory ID>

# Login
az login

# Set Subscription ID
az account set --subscription $AZURE_SUBSCRIPTION

# Create a Registered App that will be used as the "user" for the script
az ad app create --display-name tanzu-vcpu-checker \
&& AZURE_APP_ID=$(az ad app create --display-name tanzu-vcpu-checker --query appId --output tsv)

# Store this ID for future reference
echo $AZURE_APP_ID

# Grant the App Read-only access to your subscription
spid=$(az ad sp create --id $AZURE_APP_ID --query id --output tsv) \
&& az role assignment create --assignee $spid \
--role "Reader" \
--subscription $AZURE_SUBSCRIPTION \
--scope /subscriptions/$AZURE_SUBSCRIPTION

# Create the "password" for the user, this will expire in 2 years
AZURE_APP_VALUEID=$(az ad app credential reset --id $AZURE_APP_ID --append --display-name tanzu-vcpu-checker --years 2 --query password --output tsv)

# Store this password in a safe place (you can't access this again)
echo $AZURE_APP_VALUEID
```

## Install/Run via Docker

To run this locally on your laptop, easiest method is Docker.

Download this repo
```
git clone https://github.com/ryandotclair/tanzu-vcpu-checker.git
```

Create the docker image (from base Alpine image) and run it.
```
docker build -t tanzu-vcpu-checker .

docker run -it --rm -e AZURE_APP_VALUEID=$AZURE_APP_VALUEID -e AZURE_APP_ID=$AZURE_APP_ID -e AZURE_TENANTID=$AZURE_TENANTID -e AZURE_SUBSCRIPTION=$AZURE_SUBSCRIPTION tanzu-vcpu-checker
```
> Note: This run command will delete (`--rm`) the container when you exit it. Optionally you can pass in `-v .:/data` in combination with the `csv -f` feature as mentioned below to keep the data around.

# Usage
There are three ways of using this script
1. `console` mode. This gives you varying levels of information and totals.
    ```
    checker console
    ```
2. `csv` mode. This prints a csv-style output to console.
    ```
    checker csv
    ```
3. `csv --file` mode. This actually writes out to disk (the current working directory you run the script from) a csv file. It will append if the file already exists.
    ```
    checker csv -f
    ```
    > Note: Potentially run this docker image on a VM, set this script to run via a cron job once an hour (`0 * * * *`), and have it write to an NFS share, for historical purposes.

# Known Issue/Behavior
It's currently set to assume if Azure's API (against the App's Deployment) doesn't respond within 20 seconds, it will put a `TIMEOUT ERROR` in the App's Total vCPU. I've seen this occur only a handful of times and suspect it has to do with when a Deployment's Staging is getting promted to Production (however, I couldn't reproduce).

# TODO
- Turn this into an App Accelerator/API endpoint so it can optionally run on Azure Spring Apps Enterprise (for it's patching/health probes), with instructions on how to trigger it's reporting hourly, set up health probes, and redeploy automation (patching).
- Store the timeseries data into a proper database, with built in reports
- Look into breaking up the work and running each in parallel to speed up large deployments
