class UserService:
    def _init_(self, username, email):
        self.username = username
        self.email = email
        self.is_active = True

    def get_user_info(self):
        """
        Returns user information as a dictionary.
        """
        return {
            "username": self.username,
            "email": self.email,
            "active": self.is_active
        }

    def deactivate_user(self):
        """
        Deactivates the user account.
        """
        self.is_active = False

    def update_email(self, new_email):
        """
        Updates the user's email address.
        """
        self.email = new_email
