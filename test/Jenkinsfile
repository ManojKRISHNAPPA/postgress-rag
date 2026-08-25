pipeline{
    agent any

    environment {
        IMAGE_NAME = "manojkrishnappa/postgress-rag-dev:${GIT_COMMIT}"
        AWS_REGION = "ap-northeast-1"
        CLUSTER_NAME = "itkannadigaru-cluster"
        NAMESPACE = "quantam"
        SONAR_PROJECT_KEY = "postgress-rag"
        TRIVY_SEVERITY = "CRITICAL,HIGH"
        OWASP_FAIL_CVSS = "7"
    }

    options {
        timestamps()
    }

    stages{
        stage('git-checkout'){
            steps{
                git branch: 'main', url: 'https://github.com/ManojKRISHNAPPA/postgress-rag.git'  
            }    
        }

        stage('setup-python-env'){
            steps{
                sh '''
                python3 -m venv .venv
                . .venv/bin/activate
                pip install --upgrade pip
                pip install -r requirements.txt
                pip install -r requirements-dev.txt
                '''
            }
        }

        stage('unit-tests'){
            steps{
                sh '''
                . .venv/bin/activate
                pytest --junitxml=test-results/junit.xml --cov=. --cov-report=xml:coverage.xml --cov-report=html:coverage-html --cov-report=term
                '''
            }
            post{
                always{
                    junit allowEmptyResults: true, testResults: 'test-results/junit.xml'
                    publishHTML(target: [
                        allowMissing: true,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: 'coverage-html',
                        reportFiles: 'index.html',
                        reportName: 'Coverage Report'
                    ])
                }
            }
        }

        stage('mutation-testing'){
            steps{
                sh '''
                . .venv/bin/activate
                mutmut run || true
                mutmut results
                mutmut html
                '''
            }
            post{
                always{
                    archiveArtifacts allowEmptyArchive: true, artifacts: 'html/**', fingerprint: true
                    publishHTML(target: [
                        allowMissing: true,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: 'html',
                        reportFiles: 'index.html',
                        reportName: 'Mutation Testing Report'
                    ])
                }
            }
        }

        stage('owasp-dependency-check'){
            steps{
                withCredentials([string(credentialsId: 'OWASAP_NVD_KEY', variable: 'NVD_API_KEY')]) {
                    dependencyCheck additionalArguments: "--scan . --format XML --format HTML --out dependency-check-report --disableYarnAudit --disableNodeAudit --failOnCVSS ${OWASP_FAIL_CVSS} --nvdApiKey ${NVD_API_KEY}", odcInstallation: 'OWASP-Dependency-Check'
                }
                dependencyCheckPublisher pattern: 'dependency-check-report/dependency-check-report.xml'
            }
        }

        stage('sonarqube-analysis'){
            steps{
                withSonarQubeEnv('SonarQube') {
                    sh '''
                    . .venv/bin/activate
                    sonar-scanner \
                      -Dsonar.projectKey=${SONAR_PROJECT_KEY} \
                      -Dsonar.sources=. \
                      -Dsonar.python.coverage.reportPaths=coverage.xml \
                      -Dsonar.python.xunit.reportPath=test-results/junit.xml \
                      -Dsonar.exclusions=.venv/**,tests/**,html/**
                    '''
                }
            }
        }

        stage('quality-gate'){
            steps{
                timeout(time: 10, unit: 'MINUTES') {
                    waitForQualityGate abortPipeline: true
                }
            }
        }

        stage('trivy-filesystem-scan'){
            steps{
                sh '''
                trivy fs --severity ${TRIVY_SEVERITY} --exit-code 1 --no-progress --format table --output trivy-fs-report.txt .
                trivy fs --severity ${TRIVY_SEVERITY} --exit-code 0 --no-progress --format template --template "@/usr/local/share/trivy/templates/html.tpl" --output trivy-fs-report.html .
                '''
            }
            post{
                always{
                    archiveArtifacts allowEmptyArchive: true, artifacts: 'trivy-fs-report.txt,trivy-fs-report.html'
                    publishHTML(target: [
                        allowMissing: true,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: '.',
                        reportFiles: 'trivy-fs-report.html',
                        reportName: 'Trivy Filesystem Report'
                    ])
                }
            }
        }

        stage('docker-build'){
            steps{
                script{
                    sh '''
                    printenv
                    docker build -t ${IMAGE_NAME} .
                    '''
                }
            }
        }

        stage('trivy-image-scan'){
            steps{
                sh '''
                trivy image --severity ${TRIVY_SEVERITY} --exit-code 1 --no-progress --format table --output trivy-image-report.txt ${IMAGE_NAME}
                trivy image --severity ${TRIVY_SEVERITY} --exit-code 0 --no-progress --format template --template "@/usr/local/share/trivy/templates/html.tpl" --output trivy-image-report.html ${IMAGE_NAME}
                '''
            }
            post{
                always{
                    archiveArtifacts allowEmptyArchive: true, artifacts: 'trivy-image-report.txt,trivy-image-report.html'
                    publishHTML(target: [
                        allowMissing: true,
                        alwaysLinkToLastBuild: true,
                        keepAll: true,
                        reportDir: '.',
                        reportFiles: 'trivy-image-report.html',
                        reportName: 'Trivy Image Report'
                    ])
                }
            }
        }

        stage('docker-login'){
            steps{
                withCredentials([usernamePassword(credentialsId: 'dockerhub-creds', passwordVariable: 'DOCKER_PASSWORD', usernameVariable: 'DOCKER_USERNAME')]) {
                    sh '''
                    echo $DOCKER_PASSWORD | docker login -u $DOCKER_USERNAME --password-stdin
                    '''
                }
            }
        }

        stage('docker-push'){
            steps{
                sh '''
                docker push ${IMAGE_NAME}
                '''
            }
        }

        stage('update kube-config'){
            steps{
                sh '''
                    aws eks --region ${AWS_REGION} update-kubeconfig --name ${CLUSTER_NAME}
                '''
            }
        }

        stage('deploy'){
            steps{
                withKubeConfig(caCertificate: '', clusterName: 'itkannadigaru-cluster', contextName: '', credentialsId: 'kube', namespace: 'quantam', restrictKubeConfigAccess: false, serverUrl: 'https://D8C8960F77C6D66C4F891EA787E11A83.gr7.ap-northeast-1.eks.amazonaws.com') {
                    sh '''
                    sed -i "s|replace|${IMAGE_NAME}|g" Deployment.yaml
                    kubectl apply -f Deployment.yaml -n ${NAMESPACE}
                    '''
                }
            }
        }
    }

}