"""Small lab application; credentials come exclusively from the EC2 IAM role."""
import json
import logging
import os
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import boto3
from botocore.config import Config

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
db = boto3.client(
    "dynamodb",
    region_name=os.environ["AWS_DEFAULT_REGION"],
    config=Config(connect_timeout=2, read_timeout=3, retries={"max_attempts": 2}),
)
table = os.environ["TABLE_NAME"]


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/health"):
            self.respond(404, {"error": "not found"})
            return
        try:
            if self.path == "/health":
                db.describe_table(TableName=table)
                self.respond(200, {"status": "ok"})
                return
            result = db.update_item(
                TableName=table,
                Key={"id": {"S": "homepage"}},
                UpdateExpression="ADD visits :one",
                ExpressionAttributeValues={":one": {"N": "1"}},
                ReturnValues="UPDATED_NEW",
            )
            self.respond(200, {
                "project": "AWS final project",
                "instance": socket.gethostname(),
                "visits": int(result["Attributes"]["visits"]["N"]),
            })
        except Exception:
            logging.exception("DynamoDB request failed")
            self.respond(503, {"error": "database unavailable"})

    def respond(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        logging.info("%s %s", self.client_address[0], fmt % args)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
