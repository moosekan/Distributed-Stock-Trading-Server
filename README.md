## Step 1: After Cloning

```bash
cd <repository_root>
```

## Step 3: Create a Virtual Environment 

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
## Step 4: Start servers (Natively)
Note: For deploying and running server on AWS check the evaluation doc for instructions
```bash
cd src
chmod +x native_build.sh
./native_build.sh
```

## Step 5: Run Client

Inside the Activated previously created virtual environment in a new tab. The frontend HOST may need to be changed depending on where the server is running if native "localhost" if AWS then the public IP of the frontend HOST 

```bash
cd src/client
python http_client.py
```

## Step 6: To Simulate Crash Failures

```bash
cd src
chmod +x simulate_crashes.sh
./simulate_crashes.sh <replica_id (1|2|3)>
```

## Step 8: Test

From the src folder run  
```
pytest
```
This will run the file test_functional.py

To run the load test from the src/test folder run 
```
python load_testing.py
```

