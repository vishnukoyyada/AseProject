class UserService:
    def __init__(self, username, email):
        self.username = username
        self.email = email
        self.is_active = True

    def get_user_info(self):
        return {
            "username": self.username,
            "email": self.email,
            "active": self.is_active
        }

    def deactivate_user(self):
        self.is_active = False

    def update_email(self, new_email):
        self.email = new_email
