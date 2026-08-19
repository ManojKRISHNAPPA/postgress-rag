pipeline{
    agent any

    environment {
        IMAGE_NAME = "manojkrishnappa/postgress-rag-dev"
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
                    sh "docker build -t ${IMAGE_NAME} ."
                }
            }
        }
    }

}