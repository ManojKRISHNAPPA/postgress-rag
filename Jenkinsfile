pipeline{
    agent any

    environment {
        IMAGE_NAME = "manojkrishnappa/postgress-rag-dev:${GIT_COMMIT}"
        AWS_REGION = "ap-northeast-1"
        CLUSTER_NAME = "itkannadigaru-cluster"
        NAMESPACE = "quantam"
    }

    stages{
        stage('git-checkout'){
            steps{
                git branch: 'main', url: 'https://github.com/ManojKRISHNAPPA/postgress-rag.git'  
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