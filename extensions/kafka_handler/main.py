# Copyright (c) 2017, MD2K Center of Excellence
# - Nasir Ali <nasir.ali08@gmail.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import sys
import os
import argparse
from extensions.kafka_handler.core.kafka_consumer import spark_kafka_consumer
from extensions.kafka_handler.core.kafka_producer import kafka_file_to_json_producer
from pyspark.streaming import StreamingContext
from core.util.spark_helper import get_or_create_sc

def run():
    parser = argparse.ArgumentParser(description='CerebralCortex Kafka Message Handler.')
    parser.add_argument("-d", "--data_dir", help="Directory path where all the gz files are stored by API-Server", required=True)
    parser.add_argument("-bd", "--batch_duration", help="How frequent kafka messages shall be checked (duration in seconds)", required=False)
    parser.add_argument("-b", "--broker_list", help="Kafka brokers ip:port. Use comma if there are more than one broker. (e.g., 127.0.0.1:9092)", required=False)

    args = vars(parser.parse_args())

    if not str(args["data_dir"]).strip():
        raise ValueError("SqlData dir path cannot be empty.")
    else:
        data_path = str(args["data_dir"]).strip()
        if (data_path[-1] != '/'):
            data_path += '/'

    if not str(args["batch_duration"]).strip():
        batch_duration = 5  # seconds
    else:
        batch_duration = str(args["batch_duration"]).strip()

    if not str(args["broker_list"]).strip():
        broker = "localhost:9092"  # multiple brokers can be passed as comma separated values
    else:
        broker = str(args["broker_list"]).strip()

    # Kafka Consumer Configs
    ssc = StreamingContext(get_or_create_sc(type="sparkContext"), batch_duration)
    get_or_create_sc(type="sparkContext").setLogLevel("WARN")
    consumer_group_id = "md2k-test"

    kafka_files_stream = spark_kafka_consumer(["filequeue"], ssc, broker, consumer_group_id)
    kafka_files_stream.foreachRDD(lambda rdd: kafka_file_to_json_producer(rdd, data_path))

    ssc.start()
    ssc.awaitTermination()

if __name__=="__main__":
    run()

