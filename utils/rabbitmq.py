import os
import pika
from config.env import RABBITMQ_URL
from utils.constant import SPEECH_TO_TEXT_QUEUE, AUDIO_ANALYSIS_QUEUE, VIDEO_ANALYSIS_QUEUE, DLX_EXCHANGE, FAILED_STT_TASK_QUEUE, SPEECH_TO_TEXT_DELAY_QUEUE, FAILED_AUDIO_ANALYSIS_TASK_QUEUE, FAILED_VIDEO_ANALYSIS_TASK_QUEUE, AUDIO_ANALYSIS_DELAY_QUEUE, VIDEO_ANALYSIS_DELAY_QUEUE,LLM_EVALUATION_QUEUE,LLM_EVALUATION_DELAY_QUEUE,FAILED_LLM_EVALUATION_TASK_QUEUE,FINAL_INTERVIEW_EVAL_QUEUE,FINAL_INTERVIEW_EVAL_DELAY_QUEUE, FAILED_FINAL_INTERVIEW_EVAL_TASK_QUEUE, REPORT_GENERATION_PDF_QUEUE, REPORT_GENERATION_PDF_DELAY_QUEUE, FAILED_REPORT_GENERATION_PDF_TASK_QUEUE




def connect_rabbitmq():

    # --- Setup RabbitMQ Connection ---
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    return channel, connection

# channel, connection = connect_rabbitmq()


def initialize_queues(channel):
    try:
        # Declaring the Dead-letter exchange
        channel.exchange_declare(
            exchange=DLX_EXCHANGE,
            durable=True,
            exchange_type="direct"
        )


        # Declaring the Failure queues

        channel.queue_declare(queue=FAILED_STT_TASK_QUEUE, durable=True)
        channel.queue_bind(
            exchange=DLX_EXCHANGE,
            queue=FAILED_STT_TASK_QUEUE,
            routing_key="stt.failure"
        )

        channel.queue_declare(queue=FAILED_AUDIO_ANALYSIS_TASK_QUEUE, durable=True)
        channel.queue_bind(
            exchange=DLX_EXCHANGE,
            queue=FAILED_AUDIO_ANALYSIS_TASK_QUEUE,
            routing_key="audio.failure"
        )

        channel.queue_declare(queue=FAILED_VIDEO_ANALYSIS_TASK_QUEUE, durable=True)
        channel.queue_bind(
            exchange=DLX_EXCHANGE,
            queue=FAILED_VIDEO_ANALYSIS_TASK_QUEUE,
            routing_key="video.failure"
        )

        channel.queue_declare(queue=FAILED_LLM_EVALUATION_TASK_QUEUE,durable=True)
        channel.queue_bind(
            exchange=DLX_EXCHANGE,
            queue=FAILED_LLM_EVALUATION_TASK_QUEUE,
            routing_key="llm.failure"
        )

        channel.queue_declare(queue=FAILED_FINAL_INTERVIEW_EVAL_TASK_QUEUE,durable=True)
        channel.queue_bind(
            exchange=DLX_EXCHANGE,
            queue=FAILED_FINAL_INTERVIEW_EVAL_TASK_QUEUE,
            routing_key="final_interview_eval.failure"
        )

        channel.queue_declare(queue=FAILED_REPORT_GENERATION_PDF_TASK_QUEUE,durable=True)
        channel.queue_bind(
            exchange=DLX_EXCHANGE,
            queue=FAILED_REPORT_GENERATION_PDF_TASK_QUEUE,
            routing_key="report_generation_pdf.failure"
        )


        # Main Queues

        main_args_stt={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": "stt.failure"
        }

        channel.queue_declare(queue=SPEECH_TO_TEXT_QUEUE, durable=True, arguments=main_args_stt)

        main_args_audio={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": "audio.failure"
        }

        channel.queue_declare(queue=AUDIO_ANALYSIS_QUEUE, durable=True, arguments=main_args_audio)

        main_args_video={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": "video.failure"
        }

        channel.queue_declare(queue=VIDEO_ANALYSIS_QUEUE, durable=True, arguments=main_args_video)
        
        main_args_llm={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": "llm.failure"
        }

        channel.queue_declare(queue=LLM_EVALUATION_QUEUE, durable=True, arguments=main_args_llm)

        main_args_final_interview_eval={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": "final_interview_eval.failure"
        }

        channel.queue_declare(queue=FINAL_INTERVIEW_EVAL_QUEUE, durable=True, arguments=main_args_final_interview_eval)

        main_args_report_generation_pdf={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": "report_generation_pdf.failure"
        }

        channel.queue_declare(queue=REPORT_GENERATION_PDF_QUEUE, durable=True, arguments=main_args_report_generation_pdf)


        # Delay Queues

        delay_args_stt={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": SPEECH_TO_TEXT_QUEUE,
            "x-message-ttl": 10000,
        }

        channel.queue_declare(queue=SPEECH_TO_TEXT_DELAY_QUEUE, durable=True, arguments=delay_args_stt)

        delay_args_audio={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": AUDIO_ANALYSIS_QUEUE,
            "x-message-ttl": 10000,
        }

        channel.queue_declare(queue=AUDIO_ANALYSIS_DELAY_QUEUE, durable=True, arguments=delay_args_audio)

        delay_args_video={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": VIDEO_ANALYSIS_QUEUE,
            "x-message-ttl": 10000,
        }

        channel.queue_declare(queue=VIDEO_ANALYSIS_DELAY_QUEUE, durable=True, arguments=delay_args_video)
        
        delay_args_llm={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": LLM_EVALUATION_QUEUE,
            "x-message-ttl": 10000,
        }

        channel.queue_declare(queue=LLM_EVALUATION_DELAY_QUEUE, durable=True, arguments=delay_args_llm)

        delay_args_final_interview_eval={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": FINAL_INTERVIEW_EVAL_QUEUE,
            "x-message-ttl": 10000,
        }

        channel.queue_declare(queue=FINAL_INTERVIEW_EVAL_DELAY_QUEUE, durable=True, arguments=delay_args_final_interview_eval)

        delay_args_report_generation_pdf={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": REPORT_GENERATION_PDF_QUEUE,
            "x-message-ttl": 10000,
        }

        channel.queue_declare(queue=REPORT_GENERATION_PDF_DELAY_QUEUE, durable=True, arguments=delay_args_report_generation_pdf)
        
        return True
    except Exception as rabbitmq_exception:
        return False
