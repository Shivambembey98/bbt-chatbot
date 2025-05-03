import boto3
import json

aws_region = "ap-south-1"
bedrock_client = boto3.client("bedrock-runtime", region_name=aws_region)

def query_bedrock(document_text, user_query):
    model_id = "amazon.titan-text-express-v1"  # ✅ Correct Model ID for Titan Text
    
    # Titan requires "inputText" instead of "prompt"
    full_prompt = f"""Here is some context for you:
{document_text}

Now, answer this question:
{user_query}
"""

    payload = {
        "inputText": full_prompt,   # ✅ Titan expects "inputText", NOT "prompt"
        "textGenerationConfig": {   # ✅ Required for token control
            "maxTokenCount": 500,
            "stopSequences": [],
            "temperature": 0.7,
            "topP": 0.9
        }
    }

    response = bedrock_client.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(payload)
    )

    result = json.loads(response["body"].read())
    return result.get("results", [{}])[0].get("outputText", "Error: No response from model.")

# Example test call
response = query_bedrock("This is a test document.", "What is this document about?")
print(response)

