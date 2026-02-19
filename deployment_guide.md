# GCP Deployment Guide: Data Generate

This guide provides the steps to containerize and deploy the Data Generate tool to Google Cloud Platform (GCP) using Cloud Run.

## Prerequisites
1.  **Google Cloud SDK**: Installed and initialized (`gcloud init`).
2.  **Docker**: Installed and running locally.
3.  **GCP Project**: A project with billing enabled.

## 1. Setup Environment
Replace `[PROJECT_ID]` with your actual GCP project ID.

```powershell
$PROJECT_ID = "your-project-id"
gcloud config set project $PROJECT_ID
```

## 2. Enable Required APIs
Ensure the necessary GCP services are enabled:

```powershell
gcloud services enable artifactregistry.googleapis.com run.googleapis.com
```

## 3. Create Artifact Registry Repository
Create a repository to store your Docker images:

```powershell
gcloud artifacts repositories create data-generate-repo `
    --repository-format=docker `
    --location=us-central1 `
    --description="Docker repository for Data Generate tool"
```

## 4. Build and Push Image
Build the Docker image and push it to the registry.

```powershell
# Authenticate Docker to GCP
gcloud auth configure-docker us-central1-docker.pkg.dev

# Build the image
docker build -t us-central1-docker.pkg.dev/$PROJECT_ID/data-generate-repo/data-generate:latest .

# Push the image
docker push us-central1-docker.pkg.dev/$PROJECT_ID/data-generate-repo/data-generate:latest
```

## 5. Deploy to Cloud Run
Deploy the containerized application to Cloud Run:

```powershell
gcloud run deploy data-generate `
    --image us-central1-docker.pkg.dev/$PROJECT_ID/data-generate-repo/data-generate:latest `
    --platform managed `
    --region us-central1 `
    --allow-unauthenticated `
    --port 3001
```

## 6. Access the Application
Once the deployment is complete, `gcloud` will provide a Service URL (e.g., `https://data-generate-xyz.a.run.app`). You can visit this URL to access your deployed tool.

---

> [!TIP]
> **Environment Variables**: If your application requires environment variables, you can add them during deployment using the `--set-env-vars` flag.
