# ArkhRec - card & deck "recommender" for Arkham Horror: Card Game

[https://www.arkhrec.com](https://www.arkhrec.com)

ArkhRec is built with Flask

To install and run it locally:

1. Clone the repository
2. Create a virtual environment inside the repository's root directory
```
        python3 -m venv <NAME_OF_THE_VIRTUAL_ENVIRONMENT>
```    
3. Activate the virtual environment
```
        venv\Scripts\activate (in Windows)
        venv/bin/activate (in Unix)
```    
4. Install the requirements
```
        pip install requirements.txt
```    
5. Copy the .pickle files from the repository castilhocp/arkhrec-base-files to the /datafiles folder
6. Run flask
```
        python -m flask --app arkhrec run
```
It should be running on localhost:5000
