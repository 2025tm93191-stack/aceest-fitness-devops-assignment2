# ACEest Assignment 2 on the BITS VM: step-by-step with screenshots

Everything the pipeline needs (code, Jenkinsfile, Dockerfile, Kubernetes manifests, scripts) is already in GitHub:
<https://github.com/2025tm93191-stack/aceest-fitness-devops-assignment2>. On the VM you only install the tools,
connect them, and run the pipeline. 📸 marks a screenshot for the submission.

**VM needs:** Ubuntu 22.04/24.04 (x86-64), sudo, internet access, at least **4 CPUs, 8 GB RAM, 40 GB disk**.
Check with `nproc; free -h; df -h /`.

**Values used below:**

| What | Value |
|---|---|
| GitHub repo | `https://github.com/2025tm93191-stack/aceest-fitness-devops-assignment2.git` |
| Docker Hub user | `2025tm93191subhodip` |
| Docker Hub token | your `dckr_pat_...` token (create a new one for the VM if you like) |
| Jenkins job name | `aceest-fitness` |

---

## 1. Base packages

```bash
sudo apt-get update
sudo apt-get install -y git curl wget unzip ca-certificates gnupg python3 python3-venv python3-pip \
    openjdk-21-jre-headless shellcheck
```

(On Ubuntu 22.04 use `openjdk-17-jre-headless` if 21 is not available.)

## 2. Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker                       # or log out and back in
docker run --rm hello-world
```

## 3. kubectl and Minikube

```bash
curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -m 755 kubectl /usr/local/bin/kubectl && rm kubectl
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
sudo install -m 755 minikube-linux-amd64 /usr/local/bin/minikube && rm minikube-linux-amd64

minikube start --driver=docker --cpus=2 --memory=4096 --addons=ingress
kubectl get nodes
kubectl -n ingress-nginx get pods          # wait until the controller is Running
```

📸 **S1** – `kubectl get nodes` showing `minikube Ready`.

## 4. SonarQube

```bash
sudo sysctl -w vm.max_map_count=524288      # needed by SonarQube's Elasticsearch
docker run -d --name sonarqube --restart unless-stopped -p 9000:9000 sonarqube:lts-community
```

Wait about 2 minutes, then open `http://<vm-ip>:9000` (or `http://localhost:9000` in the VM browser):

1. Log in `admin` / `admin`, set a new password.
2. **Create project → Manually**: project key `aceest-fitness`, display name `ACEest Fitness & Gym`, branch `main`.
   Choose **Use the global setting**, then **Locally** → **Generate** a token. Copy it (starts with `sqp_`).
3. **Administration → Configuration → Webhooks → Create**: name `jenkins`,
   URL `http://172.17.0.1:8080/sonarqube-webhook/` (172.17.0.1 = the VM as seen from the container).

## 5. Jenkins

```bash
sudo wget -O /etc/apt/keyrings/jenkins-keyring.asc https://pkg.jenkins.io/debian-stable/jenkins.io-2023.key
echo "deb [signed-by=/etc/apt/keyrings/jenkins-keyring.asc] https://pkg.jenkins.io/debian-stable binary/" \
  | sudo tee /etc/apt/sources.list.d/jenkins.list
sudo apt-get update && sudo apt-get install -y jenkins
sudo usermod -aG docker jenkins             # Jenkins builds and runs Docker images
sudo systemctl restart jenkins
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
```

(If `apt-get update` complains about the key, take the current key file name from <https://pkg.jenkins.io/debian-stable/>.)

Open `http://<vm-ip>:8080`, paste the initial password, **Install suggested plugins**, create your admin user.

### 5.1 Plugins
**Manage Jenkins → Plugins → Available**, install and restart:
`SonarQube Scanner`, `Pipeline: Stage View`, `Docker Pipeline` (optional). Pipeline, Git, JUnit and Credentials
Binding come with the suggested plugins.

### 5.2 SonarQube Scanner tool
**Manage Jenkins → Tools → SonarQube Scanner installations → Add**: Name **`SonarScanner`** (exactly),
tick **Install automatically**, pick the latest version. Save.

### 5.3 Credentials
**Manage Jenkins → Credentials → System → Global credentials → Add Credentials**, three times:

| Kind | ID (exactly) | Value |
|---|---|---|
| Secret text | `sonar-token` | the SonarQube token from step 4 |
| Username with password | `dockerhub-creds` | username `2025tm93191subhodip`, password = Docker Hub token |
| Secret file | `kubeconfig` | the file created by the command below |

```bash
kubectl config view --flatten --minify > ~/kubeconfig-jenkins     # then upload this file
```

📸 **S2** – the credentials list showing the three IDs (values are hidden by Jenkins).

### 5.4 SonarQube server
**Manage Jenkins → System → SonarQube servers**: tick *Environment variables*, **Add SonarQube**:
Name **`SonarQube`** (exactly), URL `http://localhost:9000`, token `sonar-token`. Save.

### 5.5 Pipeline job
**New Item** → `aceest-fitness` → **Pipeline** → OK.
- *Pipeline* section: **Pipeline script from SCM** → **Git** → repository URL above → branch `*/main` →
  script path `Jenkinsfile`. Save.

📸 **S3** – job configuration showing *Pipeline script from SCM* with the GitHub URL.

## 6. Run the pipeline

1. **Build Now** once. The first build uses the defaults: SonarQube + quality gate, Docker build, Pytest inside
   the container, push to Docker Hub, rolling deploy, smoke test. It takes 5–10 minutes the first time.
2. From then on use **Build with Parameters**. Run these, one after another:

| Build | Parameters | Shows |
|---|---|---|
| A | `DEPLOY_STRATEGY=rolling`, `SIMULATE_BAD_RELEASE` ✔ | failed smoke test → **automatic rollback** (build is red on purpose) |
| B | `DEPLOY_STRATEGY=rolling` | rolling update, zero downtime |
| C | `DEPLOY_STRATEGY=blue-green` | idle colour tested, traffic switched |
| D | `DEPLOY_STRATEGY=canary`, `BASELINE_IMAGE_TAG=1.1.0`, `CANARY_WEIGHT=20` | 80/20 split between 1.1.0 and the new build |
| E | `DEPLOY_STRATEGY=ab-testing`, `BASELINE_IMAGE_TAG=1.1.0` | header-based routing |
| F | `DEPLOY_STRATEGY=shadow`, `BASELINE_IMAGE_TAG=1.1.0` | live traffic on 1.1.0, copy to the new build |

To show a blue-green switch from v1 to v2 (instead of build → build), deploy 1.1.0 first by hand, then run build C:

```bash
git clone https://github.com/2025tm93191-stack/aceest-fitness-devops-assignment2.git && cd aceest-fitness-devops-assignment2
k8s/scripts/deploy.sh blue-green 2025tm93191subhodip/aceest-fitness:1.1.0
```

Jenkins also polls GitHub every 5 minutes, so any new commit on `main` triggers a build (rolling deploy) by itself.

📸 **S4** – job page **Stage View** with green builds (all stages from Checkout to Smoke Test).
📸 **S5** – build A: stage view with the red *Smoke Test & Rollback* stage + console text
"Smoke test failed; rolling rolled back to the last stable version".
📸 **S6** – a build's **Test Result** page (JUnit, all tests passed).
📸 **S7** – a build's **Build Artifacts** list (`reports/`, `dist/…-src.tar.gz`, `…-build-info.txt`).
📸 **S8** – console log of the *Quality Gate* stage ("Quality gate status: OK") and of *Push to Docker Hub*.

## 7. SonarQube results

Open `http://<vm-ip>:9000/dashboard?id=aceest-fitness`.

📸 **S9** – project overview: Quality Gate **Passed**, bugs, vulnerabilities, coverage, duplications.
📸 **S10** – *Activity* tab (one analysis per build) or *Issues* tab.

For a "SonarQube report" file: each build archives `reports/sonar-quality-gate.json` and
`reports/sonar-measures.json`; you can also print the dashboard to PDF from the browser.

## 8. Docker Hub

Open <https://hub.docker.com/r/2025tm93191subhodip/aceest-fitness/tags>.

📸 **S11** – tags list: `1.0.0`, `1.1.0`, `2.0.0`, `latest`, `2.0.0-b<N>` (one per Jenkins build).

## 9. The running cluster and each strategy

```bash
cd ~/aceest-fitness-devops-assignment2        # the clone from step 6
k8s/scripts/status.sh                         # what runs where, for every strategy
kubectl get pods -A | grep aceest
```

📸 **S12** – `k8s/scripts/status.sh` output (all five namespaces, images, ingress, live colour).

Make the ingress reachable on the VM's port 8081 (leave this running in its own terminal):

```bash
kubectl -n ingress-nginx port-forward --address 0.0.0.0 svc/ingress-nginx-controller 8081:80
```

In another terminal:

```bash
URL=http://localhost:8081
curl $URL/rolling/version; echo
curl $URL/blue-green/version; echo
k8s/scripts/traffic.sh $URL canary 50                       # ~80% 1.1.0 / ~20% new build
k8s/scripts/traffic.sh $URL ab 10                           # everyone: variant A (1.1.0)
k8s/scripts/traffic.sh $URL ab 10 -H 'X-User-Group: B'      # group B: variant B (new build)
k8s/scripts/traffic.sh $URL shadow 20                       # users only see the primary (1.1.0)
kubectl -n aceest-shadow logs deploy/aceest-shadow --tail=20 | grep -v kube-probe   # mirrored copies arrived
```

📸 **S13** – rolling + blue-green `curl …/version` outputs.
📸 **S14** – canary split from `traffic.sh`.
📸 **S15** – A/B: the two `traffic.sh ab` runs (with and without the header).
📸 **S16** – shadow: `traffic.sh shadow` + shadow pod log with the mirrored requests.
📸 **S17** – rollbacks by hand (optional, besides build A):

```bash
k8s/scripts/rollback.sh blue-green      # live traffic back to the previous colour
curl $URL/blue-green/version; echo
k8s/scripts/rollback.sh canary          # canary removed, 100% stable
k8s/scripts/traffic.sh $URL canary 20
kubectl -n aceest-rolling rollout history deployment/aceest
```

Browser: `http://<vm-ip>:8081/rolling/` shows the home page with the version in the footer.
📸 **S18** – home page in the browser.

## 10. Endpoint URL for the submission

- **Inside the BITS network:** `http://<vm-ip>:8081/<strategy>/` (keep the port-forward from step 9 running;
  check the VM firewall allows 8081: `sudo ufw allow 8081/tcp` if ufw is active).
- **Public:** install ngrok (`sudo snap install ngrok`), `ngrok config add-authtoken <token>`, then
  `ngrok http 8081`. Submit the `https://….ngrok-free.app` URL with the paths:
  `/rolling/`, `/blue-green/`, `/canary/`, `/ab/`, `/shadow/` (each also has `/version`, `/health`, `/api/programs`).
  The URL works only while the VM, the port-forward and ngrok keep running.

📸 **S19** – the public URL opened in a browser (e.g. `/canary/version`).

## 11. GitHub evidence

📸 **S20** – repository *Actions* tab with green runs.
📸 **S21** – *Pull requests → Closed* (feature/ci/fix/docs branches merged) and *Tags* (`v1.0.0`, `v1.1.0`, `v2.0.0`).
📸 **S22** – *Insights → Network* or `git log --graph --oneline --all | head -40` showing the merge commits.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `permission denied ... docker.sock` in Jenkins | `sudo usermod -aG docker jenkins && sudo systemctl restart jenkins` |
| Quality Gate stage waits forever | the SonarQube webhook URL (step 4.3) must reach Jenkins: `docker exec sonarqube wget -qO- http://172.17.0.1:8080/login >/dev/null && echo ok` |
| `tool 'SonarScanner' not found` / `No SonarQube server 'SonarQube'` | names in 5.2 / 5.4 must match exactly |
| SonarQube container exits | `sudo sysctl -w vm.max_map_count=524288`, then `docker start sonarqube` |
| Deploy stage: `connection refused` to the cluster | `minikube status`; if Minikube restarted, recreate `~/kubeconfig-jenkins` and re-upload the `kubeconfig` credential |
| Pods `ImagePullBackOff` | check the image exists on Docker Hub (step 8) and the VM has internet access |
| Out of memory | stop other containers; use `minikube start --memory=3072`; restart SonarQube last |

**Note:** builds on the VM push x86-64 images and re-tag `2.0.0` and `latest`; the released `1.0.0`, `1.1.0`,
`2.0.0` tags were pushed for both x86-64 and ARM, and every build also has its own `2.0.0-b<N>` tag.
