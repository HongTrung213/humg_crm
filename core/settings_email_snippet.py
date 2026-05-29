# ==========================
# EMAIL CONFIG - HUMG CRM
# ==========================
# Cách dùng test an toàn: giữ console backend để email in ra terminal, chưa gửi thật.
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = 'Trung tâm Ngoại ngữ - Tin học HUMG <no-reply@humg.edu.vn>'

# Khi gửi thật bằng Gmail SMTP, đổi sang cấu hình dưới đây:
# EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
# EMAIL_HOST = 'smtp.gmail.com'
# EMAIL_PORT = 587
# EMAIL_USE_TLS = True
# EMAIL_HOST_USER = 'email_gui_cua_ban@gmail.com'
# EMAIL_HOST_PASSWORD = 'app_password_cua_gmail'
# DEFAULT_FROM_EMAIL = 'Trung tâm Ngoại ngữ - Tin học HUMG <email_gui_cua_ban@gmail.com>'
