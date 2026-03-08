from twilio.rest import Client

# Your Account SID and Auth Token from console.twilio.com
account_sid = "ACc01193c3b63ed4f5c514e3105c159c11"
auth_token  = "5761cedc141906f8e8b2750ab03979f4"

client = Client(account_sid, auth_token)

message = client.messages.create(
    to="+573133047737",
    from_="+15077768269",
    body="Hey, you're awesome, a total pro, and this year you're going to kill it at everything you do. You're the best, always, always, always... So let's get serious about this cryptography stuff and create our own company. Go Juacho this year!")

print(message.sid)
