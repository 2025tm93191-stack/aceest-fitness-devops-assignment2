// ACEest Fitness & Gym - Jenkins CI/CD pipeline
//
// Checkout -> clean venv -> lint -> unit tests -> SonarQube analysis -> quality gate
// -> Docker build -> tests inside the container -> push to Docker Hub
// -> deploy to Kubernetes (chosen strategy) -> smoke test -> automatic rollback on failure.
//
// One-time Jenkins setup (see README "Jenkins Setup"):
//   Plugins:      Pipeline, Git, JUnit, Credentials Binding, SonarQube Scanner
//   Tools:        SonarQube Scanner installation named 'SonarScanner'
//   System:       SonarQube server named 'SonarQube' (+ webhook <jenkins>/sonarqube-webhook/ in SonarQube)
//   Credentials:  'dockerhub-creds' (username + access token), 'kubeconfig' (secret file)
//   Agent:        python3, docker, kubectl

// Docker Hub account the images are pushed to: change once, or override per build.
def DEFAULT_DOCKERHUB_USER = '2025tm93191subhodip'

pipeline {
    agent any

    // Poll GitHub every 5 minutes. With a GitHub webhook pointing at
    // http://<jenkins-host>/github-webhook/, replace with githubPush() for instant builds.
    triggers {
        pollSCM('H/5 * * * *')
    }

    parameters {
        choice(name: 'DEPLOY_STRATEGY',
               choices: ['rolling', 'blue-green', 'canary', 'ab-testing', 'shadow', 'none'],
               description: 'Kubernetes deployment strategy for this build (polled builds use the first: rolling)')
        string(name: 'BASELINE_IMAGE_TAG', defaultValue: '',
               description: 'canary / ab-testing / shadow, first deploy only: tag that keeps most of the traffic, e.g. 1.1.0')
        string(name: 'CANARY_WEIGHT', defaultValue: '20', description: 'Percentage of traffic sent to the canary')
        string(name: 'DOCKERHUB_USER', defaultValue: DEFAULT_DOCKERHUB_USER, description: 'Docker Hub account / namespace')
        booleanParam(name: 'RUN_SONAR', defaultValue: true, description: 'Run SonarQube analysis and quality gate')
        booleanParam(name: 'PUSH_IMAGE', defaultValue: true, description: 'Push the image to Docker Hub')
        booleanParam(name: 'SIMULATE_BAD_RELEASE', defaultValue: false,
                     description: 'Demo: make the post-deploy smoke test fail to show the automatic rollback')
    }

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '15'))
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    // Parameters are null on the very first run of a new job.
                    env.STRATEGY = params.DEPLOY_STRATEGY ?: 'rolling'
                    env.APP_VERSION = readFile('VERSION').trim()
                    env.IMAGE = "${params.DOCKERHUB_USER ?: DEFAULT_DOCKERHUB_USER}/aceest-fitness"
                    env.IMAGE_TAG = "${env.APP_VERSION}-b${env.BUILD_NUMBER}"
                    env.GIT_TAG = sh(script: 'git describe --tags --exact-match 2>/dev/null || true', returnStdout: true).trim()
                    currentBuild.displayName = "#${env.BUILD_NUMBER} v${env.APP_VERSION}"
                    currentBuild.description = "${env.IMAGE}:${env.IMAGE_TAG} -> ${env.STRATEGY}"
                }
                sh 'mkdir -p reports dist'
            }
        }

        stage('Clean Environment') {
            steps {
                sh '''
                    rm -rf .venv reports/* dist/*
                    python3 -m venv .venv
                    . .venv/bin/activate
                    pip install --upgrade pip
                    pip install -r requirements-dev.txt
                '''
            }
        }

        stage('Lint') {
            steps {
                sh '''
                    . .venv/bin/activate
                    python -m compileall -q app.py ACEest_Fitness.py fitness tests
                    flake8 .
                    if command -v shellcheck >/dev/null; then shellcheck -x k8s/scripts/*.sh; else echo "shellcheck not installed, skipped"; fi
                '''
            }
        }

        stage('Unit Tests') {
            steps {
                sh '''
                    . .venv/bin/activate
                    pytest --junitxml=reports/junit.xml --cov --cov-report=term --cov-report=xml:reports/coverage.xml
                '''
            }
        }

        stage('SonarQube Analysis') {
            when { expression { params.RUN_SONAR != false } }
            steps {
                script {
                    def scannerHome = tool 'SonarScanner'
                    withSonarQubeEnv('SonarQube') {
                        sh "${scannerHome}/bin/sonar-scanner -Dsonar.projectVersion=${env.APP_VERSION}"
                    }
                }
            }
        }

        stage('Quality Gate') {
            when { expression { params.RUN_SONAR != false } }
            steps {
                timeout(time: 10, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
            post {
                always {
                    // Keep the SonarQube result with the build as the "SonarQube report".
                    withSonarQubeEnv('SonarQube') {
                        sh '''
                            curl -fsS -u "$SONAR_AUTH_TOKEN:" -o reports/sonar-quality-gate.json \
                                "$SONAR_HOST_URL/api/qualitygates/project_status?projectKey=aceest-fitness" || true
                            curl -fsS -u "$SONAR_AUTH_TOKEN:" -o reports/sonar-measures.json \
                                "$SONAR_HOST_URL/api/measures/component?component=aceest-fitness&metricKeys=alert_status,bugs,vulnerabilities,security_hotspots,code_smells,coverage,duplicated_lines_density,ncloc,reliability_rating,security_rating,sqale_rating" || true
                            cp .scannerwork/report-task.txt reports/sonar-report-task.txt 2>/dev/null || true
                        '''
                    }
                }
            }
        }

        stage('Docker Build') {
            steps {
                sh '''
                    docker build --target runtime --build-arg APP_VERSION="$APP_VERSION" \
                        -t "$IMAGE:$IMAGE_TAG" -t "$IMAGE:$APP_VERSION" -t "$IMAGE:latest" .
                    if [ -n "$GIT_TAG" ]; then docker tag "$IMAGE:$IMAGE_TAG" "$IMAGE:$GIT_TAG"; fi
                '''
            }
        }

        stage('Container Tests') {
            steps {
                sh '''
                    docker build --target test -t aceest-fitness:test .
                    docker run --rm aceest-fitness:test
                    # The runtime image must start and report the right version.
                    docker rm -f "aceest-ci-$BUILD_NUMBER" 2>/dev/null || true
                    docker run -d --name "aceest-ci-$BUILD_NUMBER" "$IMAGE:$IMAGE_TAG"
                    ok=""
                    for i in $(seq 1 15); do
                        if docker exec "aceest-ci-$BUILD_NUMBER" python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:5000/version').read().decode())" > reports/container-version.json 2>/dev/null; then ok=1; break; fi
                        sleep 2
                    done
                    docker rm -f "aceest-ci-$BUILD_NUMBER"
                    [ -n "$ok" ] || { echo "runtime container did not start"; exit 1; }
                    cat reports/container-version.json
                    grep -q "\\"version\\":\\"$APP_VERSION\\"" reports/container-version.json
                '''
            }
        }

        stage('Push to Docker Hub') {
            when { expression { params.PUSH_IMAGE != false } }
            steps {
                withCredentials([usernamePassword(credentialsId: 'dockerhub-creds',
                                                  usernameVariable: 'DOCKERHUB_LOGIN',
                                                  passwordVariable: 'DOCKERHUB_TOKEN')]) {
                    sh '''
                        echo "$DOCKERHUB_TOKEN" | docker login -u "$DOCKERHUB_LOGIN" --password-stdin
                        docker push "$IMAGE:$IMAGE_TAG"
                        docker push "$IMAGE:$APP_VERSION"
                        docker push "$IMAGE:latest"
                        if [ -n "$GIT_TAG" ]; then docker push "$IMAGE:$GIT_TAG"; fi
                    '''
                }
            }
            post {
                always { sh 'docker logout || true' }
            }
        }

        stage('Build Artifacts') {
            steps {
                sh '''
                    git archive --format=tar.gz --prefix="aceest-fitness-$APP_VERSION/" \
                        -o "dist/aceest-fitness-$APP_VERSION-b$BUILD_NUMBER-src.tar.gz" HEAD
                    {
                        echo "version=$APP_VERSION"
                        echo "build=$BUILD_NUMBER"
                        echo "commit=$(git rev-parse HEAD)"
                        echo "git_tag=${GIT_TAG:-none}"
                        echo "image=$IMAGE:$IMAGE_TAG"
                        echo "image_id=$(docker image inspect --format '{{.Id}}' "$IMAGE:$IMAGE_TAG")"
                    } > "dist/aceest-fitness-$APP_VERSION-b$BUILD_NUMBER-build-info.txt"
                    cat dist/*-build-info.txt
                '''
            }
        }

        stage('Deploy to Kubernetes') {
            when { expression { env.STRATEGY != 'none' } }
            steps {
                withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
                    script {
                        try {
                            sh '''
                                BASELINE=""
                                if [ -n "$BASELINE_IMAGE_TAG" ]; then BASELINE="$IMAGE:$BASELINE_IMAGE_TAG"; fi
                                CANARY_WEIGHT="$CANARY_WEIGHT" EXPECTED_VERSION="$APP_VERSION" \
                                    k8s/scripts/deploy.sh "$STRATEGY" "$IMAGE:$IMAGE_TAG" $BASELINE
                            '''
                        } catch (err) {
                            // Blue-green switches traffic only after the idle colour passed its
                            // smoke test, so a failure here never reached users.
                            if (env.STRATEGY != 'blue-green') {
                                sh 'k8s/scripts/rollback.sh "$STRATEGY"'
                            }
                            error("Deployment failed (${err}); ${env.STRATEGY} rolled back to the last stable version")
                        }
                    }
                }
            }
        }

        stage('Smoke Test & Rollback') {
            when { expression { env.STRATEGY != 'none' } }
            steps {
                withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
                    script {
                        def expected = params.SIMULATE_BAD_RELEASE ? '0.0.0-simulated-bad-release' : env.APP_VERSION
                        try {
                            withEnv(["EXPECTED=${expected}"]) {
                                sh 'rc=0; k8s/scripts/smoke-test.sh "$STRATEGY" "$EXPECTED" > reports/smoke-test.txt 2>&1 || rc=$?; cat reports/smoke-test.txt; exit $rc'
                            }
                            sh 'k8s/scripts/status.sh "$STRATEGY" > reports/k8s-status.txt 2>&1 || true; cat reports/k8s-status.txt'
                        } catch (err) {
                            sh 'rc=0; k8s/scripts/rollback.sh "$STRATEGY" > reports/rollback.txt 2>&1 || rc=$?; cat reports/rollback.txt; exit $rc'
                            error("Smoke test failed; ${env.STRATEGY} rolled back to the last stable version")
                        }
                    }
                }
            }
        }
    }

    post {
        always {
            junit allowEmptyResults: true, testResults: 'reports/junit.xml'
            archiveArtifacts artifacts: 'reports/**, dist/**', allowEmptyArchive: true, fingerprint: true
            sh 'docker image prune -f || true'
        }
        success { echo "Build ${env.BUILD_NUMBER}: ${env.IMAGE}:${env.IMAGE_TAG} passed the quality gate and was deployed (${env.STRATEGY})." }
        failure { echo "Build ${env.BUILD_NUMBER} failed. Check the stage logs above." }
    }
}
