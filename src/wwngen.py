import uuid

def main():
	sas_address = "naa.6001405%s" % str(uuid.uuid4())[:10]
	print sas_address.replace('-', '')

if __name__ == "__main__":
    main()
