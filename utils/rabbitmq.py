import os
import pika
from config.env import RABBITMQ_URL
from utils.constant import (
    # Resume
    RESUME_ANALYSIS_QUEUE,
    RESUME_ANALYSIS_DELAY_QUEUE,
    FAILED_RESUME_ANALYSIS_TASK_QUEUE,

    # Speech to Text
    SPEECH_TO_TEXT_QUEUE,
    SPEECH_TO_TEXT_DELAY_QUEUE,
    FAILED_STT_TASK_QUEUE,

    # Audio Analysis
    AUDIO_ANALYSIS_QUEUE,
    AUDIO_ANALYSIS_DELAY_QUEUE,
    FAILED_AUDIO_ANALYSIS_TASK_QUEUE,

    # Video Analysis
    VIDEO_ANALYSIS_QUEUE,
    VIDEO_ANALYSIS_DELAY_QUEUE,
    FAILED_VIDEO_ANALYSIS_TASK_QUEUE,

    # LLM Evaluation
    LLM_EVALUATION_QUEUE,
    LLM_EVALUATION_DELAY_QUEUE,
    FAILED_LLM_EVALUATION_TASK_QUEUE,

    # Final Interview Evaluation
    FINAL_INTERVIEW_EVAL_QUEUE,
    FINAL_INTERVIEW_EVAL_DELAY_QUEUE,
    FAILED_FINAL_INTERVIEW_EVAL_TASK_QUEUE,

    # Report Generation
    REPORT_GENERATION_PDF_QUEUE,
    REPORT_GENERATION_PDF_DELAY_QUEUE,
    FAILED_REPORT_GENERATION_PDF_TASK_QUEUE,

    # Candidate Profile Embeddings
    CANDIDATE_PROFILE_EMBEDDINGS_QUEUE,
    CANDIDATE_PROFILE_EMBEDDINGS_DELAY_QUEUE,
    FAILED_CANDIDATE_PROFILE_EMBEDDINGS_TASK_QUEUE,

    # Job Description Embeddings
    JOB_DESCRIPTION_EMBEDDINGS_QUEUE,
    JOB_DESCRIPTION_EMBEDDINGS_DELAY_QUEUE,
    FAILED_JOB_DESCRIPTION_EMBEDDINGS_TASK_QUEUE,

    # Company KB Embeddings (from feat/chatv2)
    COMPANY_KB_EMBEDDINGS_QUEUE,
    FAILED_COMPANY_KB_EMBEDDINGS_TASK_QUEUE,

    # Job Recommendation
    JOB_RECOMMENDATION_QUEUE,
    JOB_RECOMMENDATION_DELAY_QUEUE,
    FAILED_JOB_RECOMMENDATION_TASK_QUEUE,

    # Send Hiring Email (from merge)
    SEND_HIRING_EMAIL_QUEUE,
    SEND_HIRING_EMAIL_DELAY_QUEUE,
    FAILED_SEND_HIRING_EMAIL_TASK_QUEUE,

    # Send Rejection Email (from merge)
    SEND_REJECTION_EMAIL_QUEUE,
    SEND_REJECTION_EMAIL_DELAY_QUEUE,
    FAILED_SEND_REJECTION_EMAIL_TASK_QUEUE,

    # Exchange
    DLX_EXCHANGE,
)




def connect_rabbitmq():

    # --- Setup RabbitMQ Connection ---
    params = pika.URLParameters(RABBITMQ_URL)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    return channel, connection

# channel, connection = connect_rabbitmq()


def _queue_declare_with_recreate(channel, queue, durable=True, arguments=None, connection=None):
    try:
        channel.queue_declare(queue=queue, durable=durable, arguments=arguments)
        return channel
    except pika.exceptions.ChannelClosedByBroker as exc:
        if connection is None:
            connection = getattr(channel, "connection", None)
        if connection is None:
            raise

        message = str(exc)
        if "inequivalent arg" in message:
            new_channel = connection.channel()
            new_channel.queue_delete(queue=queue)
            new_channel.queue_declare(queue=queue, durable=durable, arguments=arguments)
            return new_channel
        raise


def initialize_queues(channel):
    connection = getattr(channel, "connection", None)
    try:
        # Declaring the Dead-letter exchange
        channel.exchange_declare(
            exchange=DLX_EXCHANGE,
            durable=True,
            exchange_type="direct"
        )


        # Declaring the Failure queues

        # 1. STT Failure Queue
        channel.queue_declare(queue=FAILED_STT_TASK_QUEUE, durable=True)
        channel.queue_bind(
            exchange=DLX_EXCHANGE,
            queue=FAILED_STT_TASK_QUEUE,
            routing_key="stt.failure"
        )

        # 2. Audio Failure Queue
        channel.queue_declare(queue=FAILED_AUDIO_ANALYSIS_TASK_QUEUE, durable=True)
        channel.queue_bind(
            exchange=DLX_EXCHANGE,
            queue=FAILED_AUDIO_ANALYSIS_TASK_QUEUE,
            routing_key="audio.failure"
        )

        # 3. Video Failure Queue
        channel.queue_declare(queue=FAILED_VIDEO_ANALYSIS_TASK_QUEUE, durable=True)
        channel.queue_bind(
            exchange=DLX_EXCHANGE,
            queue=FAILED_VIDEO_ANALYSIS_TASK_QUEUE,
            routing_key="video.failure"
        )

        # 4. LLM Failure Queue
        channel.queue_declare(queue=FAILED_LLM_EVALUATION_TASK_QUEUE,durable=True)
        channel.queue_bind(
            exchange=DLX_EXCHANGE,
            queue=FAILED_LLM_EVALUATION_TASK_QUEUE,
            routing_key="llm.failure"
        )

        # 5. Final Interview Failure Queue
        channel.queue_declare(queue=FAILED_FINAL_INTERVIEW_EVAL_TASK_QUEUE,durable=True)
        channel.queue_bind(
            exchange=DLX_EXCHANGE,
            queue=FAILED_FINAL_INTERVIEW_EVAL_TASK_QUEUE,
            routing_key="final_interview_eval.failure"
        )

        # 6. Report Generation PDF Failure Queue
        channel.queue_declare(queue=FAILED_REPORT_GENERATION_PDF_TASK_QUEUE,durable=True)
        channel.queue_bind(
            exchange=DLX_EXCHANGE,
            queue=FAILED_REPORT_GENERATION_PDF_TASK_QUEUE,
            routing_key="report_generation_pdf.failure"
        )
        
        # 7. Candidate Profile Embedding Failure Queue
        channel.queue_declare(queue=FAILED_CANDIDATE_PROFILE_EMBEDDINGS_TASK_QUEUE,durable=True)
        channel.queue_bind(
            exchange=DLX_EXCHANGE,
            queue=FAILED_CANDIDATE_PROFILE_EMBEDDINGS_TASK_QUEUE,
            routing_key="candidate_profile_embeddings.failure"
        )
        
        # 8. Job Description Embedding Failure Queue
        channel.queue_declare(queue=FAILED_JOB_DESCRIPTION_EMBEDDINGS_TASK_QUEUE,durable=True)
        channel.queue_bind(
            exchange=DLX_EXCHANGE,
            queue=FAILED_JOB_DESCRIPTION_EMBEDDINGS_TASK_QUEUE,
            routing_key="job_description_embeddings.failure"
        )

        # 8b. Company KB Embedding Failure Queue
        channel.queue_declare(queue=FAILED_COMPANY_KB_EMBEDDINGS_TASK_QUEUE, durable=True)
        channel.queue_bind(
            exchange=DLX_EXCHANGE,
            queue=FAILED_COMPANY_KB_EMBEDDINGS_TASK_QUEUE,
            routing_key="company_kb_embeddings.failure"
        )
        
        # 9. Job Recommendation Failure Queue
        channel.queue_declare(queue=FAILED_JOB_RECOMMENDATION_TASK_QUEUE,durable=True)
        channel.queue_bind(
            exchange=DLX_EXCHANGE,
            queue=FAILED_JOB_RECOMMENDATION_TASK_QUEUE,
            routing_key="job_recommendation.failure"
        )
        
        # 10. Resume Analysis Failure Queue
        channel.queue_declare(queue=FAILED_RESUME_ANALYSIS_TASK_QUEUE,durable=True)
        channel.queue_bind(
            exchange=DLX_EXCHANGE,
            queue=FAILED_RESUME_ANALYSIS_TASK_QUEUE,
            routing_key="resume_analysis.failure"
        )
        
        # 11. Send Hiring Email Failure Queue
        channel.queue_declare(queue=FAILED_SEND_HIRING_EMAIL_TASK_QUEUE,durable=True)
        channel.queue_bind(
            exchange=DLX_EXCHANGE,
            queue=FAILED_SEND_HIRING_EMAIL_TASK_QUEUE,
            routing_key="send_hiring_email.failure"
        )
        
        # 12. Send Rejection Email Failure Queue
        channel.queue_declare(queue=FAILED_SEND_REJECTION_EMAIL_TASK_QUEUE,durable=True)    
        channel.queue_bind(
            exchange=DLX_EXCHANGE,
            queue=FAILED_SEND_REJECTION_EMAIL_TASK_QUEUE,
            routing_key="send_rejection_email.failure"
        )

        # Main Queues

        # 1. Speech to Text Queue
        main_args_stt={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": "stt.failure"
        }
        channel.queue_declare(queue=SPEECH_TO_TEXT_QUEUE, durable=True, arguments=main_args_stt)

        # 2. Audio Analysis Queue
        main_args_audio={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": "audio.failure"
        }
        channel.queue_declare(queue=AUDIO_ANALYSIS_QUEUE, durable=True, arguments=main_args_audio)

        # 3. Video Analysis Queue
        main_args_video={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": "video.failure"
        }
        channel.queue_declare(queue=VIDEO_ANALYSIS_QUEUE, durable=True, arguments=main_args_video)

        # 4. LLM Evaluation Queue
        main_args_llm={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": "llm.failure"
        }
        channel.queue_declare(queue=LLM_EVALUATION_QUEUE, durable=True, arguments=main_args_llm)

        # 5. Final Interview Evaluation Queue
        main_args_final_interview_eval={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": "final_interview_eval.failure"
        }
        channel.queue_declare(queue=FINAL_INTERVIEW_EVAL_QUEUE, durable=True, arguments=main_args_final_interview_eval)

        # 6. Report Generation Queue
        main_args_report_generation_pdf={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": "report_generation_pdf.failure"
        }
        channel.queue_declare(queue=REPORT_GENERATION_PDF_QUEUE, durable=True, arguments=main_args_report_generation_pdf)

        # 7. Candidate Profile Embeddings Queue
        main_args_candidate_profile_embeddings={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": "candidate_profile_embeddings.failure"
        }
        channel.queue_declare(queue=CANDIDATE_PROFILE_EMBEDDINGS_QUEUE, durable=True, arguments=main_args_candidate_profile_embeddings)
        
        # 8. Job Description Embeddings Queue
        main_args_job_description_embeddings={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": "job_description_embeddings.failure"
        }
        channel.queue_declare(queue=JOB_DESCRIPTION_EMBEDDINGS_QUEUE, durable=True, arguments=main_args_job_description_embeddings)

        # 8b. Company KB Embeddings Queue
        main_args_company_kb_embeddings={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": "company_kb_embeddings.failure"
        }
        channel = _queue_declare_with_recreate(
            channel,
            queue=COMPANY_KB_EMBEDDINGS_QUEUE,
            durable=True,
            arguments=main_args_company_kb_embeddings,
            connection=connection,
        )
        
        # 9. Job Recommendation Queue
        main_args_job_recommendation={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": "job_recommendation.failure"
        }
        channel.queue_declare(queue=JOB_RECOMMENDATION_QUEUE, durable=True, arguments=main_args_job_recommendation)
        
        # 10. Resume Analysis Queue
        main_args_resume_analysis={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": "resume_analysis.failure"
        }
        channel.queue_declare(queue=RESUME_ANALYSIS_QUEUE, durable=True, arguments=main_args_resume_analysis)
        
        # 11. Send Hiring Email Queue
        main_args_send_hiring_email={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": "send_hiring_email.failure"
        }
        channel.queue_declare(queue=SEND_HIRING_EMAIL_QUEUE, durable=True, arguments=main_args_send_hiring_email)
        
        # 12. Send Rejection Email Queue
        main_args_send_rejection_email={
            "x-dead-letter-exchange": DLX_EXCHANGE,
            "x-dead-letter-routing-key": "send_rejection_email.failure"
        }
        channel.queue_declare(queue=SEND_REJECTION_EMAIL_QUEUE, durable=True, arguments=main_args_send_rejection_email)
        

        # Delay Queues
        
        # 1. Speech to Text Delay Queue
        delay_args_stt={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": SPEECH_TO_TEXT_QUEUE,
            "x-message-ttl": 10000,
        }
        channel.queue_declare(queue=SPEECH_TO_TEXT_DELAY_QUEUE, durable=True, arguments=delay_args_stt)

        # 2. Audio Analysis Delay Queue
        delay_args_audio={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": AUDIO_ANALYSIS_QUEUE,
            "x-message-ttl": 10000,
        }
        channel.queue_declare(queue=AUDIO_ANALYSIS_DELAY_QUEUE, durable=True, arguments=delay_args_audio)

        # 3. Video Analysis Delay Queue
        delay_args_video={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": VIDEO_ANALYSIS_QUEUE,
            "x-message-ttl": 10000,
        }
        channel.queue_declare(queue=VIDEO_ANALYSIS_DELAY_QUEUE, durable=True, arguments=delay_args_video)

        # 4. LLM Evaluation Delay Queue
        delay_args_llm={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": LLM_EVALUATION_QUEUE,
            "x-message-ttl": 10000,
        }
        channel.queue_declare(queue=LLM_EVALUATION_DELAY_QUEUE, durable=True, arguments=delay_args_llm)

        # 5. Final Interview Evaluation Delay Queue
        delay_args_final_interview_eval={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": FINAL_INTERVIEW_EVAL_QUEUE,
            "x-message-ttl": 10000,
        }
        channel.queue_declare(queue=FINAL_INTERVIEW_EVAL_DELAY_QUEUE, durable=True, arguments=delay_args_final_interview_eval)

        # 6. Report Generation PDF Delay Queue
        delay_args_report_generation_pdf={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": REPORT_GENERATION_PDF_QUEUE,
            "x-message-ttl": 10000,
        }
        channel.queue_declare(queue=REPORT_GENERATION_PDF_DELAY_QUEUE, durable=True, arguments=delay_args_report_generation_pdf)
        
        # 7. Candidate Profile Embeddings Delay Queue
        delay_args_candidate_profile_embeddings={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": CANDIDATE_PROFILE_EMBEDDINGS_QUEUE,
            "x-message-ttl": 10000,
        }
        channel.queue_declare(queue=CANDIDATE_PROFILE_EMBEDDINGS_DELAY_QUEUE, durable=True, arguments=delay_args_candidate_profile_embeddings)
        
        # 8. Job Description Embeddings Delay Queue
        delay_args_job_description_embeddings={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": JOB_DESCRIPTION_EMBEDDINGS_QUEUE,
            "x-message-ttl": 10000,
        }
        channel.queue_declare(queue=JOB_DESCRIPTION_EMBEDDINGS_DELAY_QUEUE, durable=True, arguments=delay_args_job_description_embeddings)
        
        # 9. Job Recommendation Delay Queue
        delay_args_job_recommendation={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": JOB_RECOMMENDATION_QUEUE,
            "x-message-ttl": 10000,
        }
        channel.queue_declare(queue=JOB_RECOMMENDATION_DELAY_QUEUE, durable=True, arguments=delay_args_job_recommendation)
        
        # 10. Resume Analysis Delay Queue
        delay_args_resume_analysis={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": RESUME_ANALYSIS_QUEUE,
            "x-message-ttl": 10000,
        }
        channel.queue_declare(queue=RESUME_ANALYSIS_DELAY_QUEUE, durable=True, arguments=delay_args_resume_analysis)
        
        # 11. Send Hiring Email Delay Queue
        delay_args_send_hiring_email={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": SEND_HIRING_EMAIL_QUEUE,
            "x-message-ttl": 10000,
        }
        channel.queue_declare(queue=SEND_HIRING_EMAIL_DELAY_QUEUE, durable=True, arguments=delay_args_send_hiring_email)

        # 12. Send Rejection Email Delay Queue
        delay_args_send_rejection_email={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": SEND_REJECTION_EMAIL_QUEUE,
            "x-message-ttl": 10000,
        }
        channel.queue_declare(queue=SEND_REJECTION_EMAIL_DELAY_QUEUE, durable=True, arguments=delay_args_send_rejection_email)
        return channel
    except Exception as rabbitmq_exception:
        print(f"Error initializing RabbitMQ queues: {rabbitmq_exception}")
        raise rabbitmq_exception
