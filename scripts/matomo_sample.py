from friday_night_assistant.matomo.client import MatomoClient, get_all_sites_data
import os


def main():
    # Allow override via env, otherwise use env
    base = os.environ.get("MATOMO_URL")
    token = os.environ.get("MATOMO_AUTH_TOKEN")
    if not base or not token:
        print("MATOMO_URL or MATOMO_AUTH_TOKEN not set - set them and re-run")
        return

    client = MatomoClient()
    data = get_all_sites_data(client, site_ids=(1, 2, 3), period="day", date="yesterday")
    for sid, d in data.items():
        print("Site:", sid)
        print(d)


if __name__ == "__main__":
    main()

