# Isaac Mission Dispatch Security considerations
Isaac provides a reference copy of Isaac Cloud Services which allow for API based submission of missions to enable Edge/Cloud control of robots.  The reference is intended to work on a limited access workstation to demonstrate functionality and should not be considered secure.  The following details outline security parameters to safely deploy locally and understand exercises needed for a secure production deployment.

## Containerized services
All local services are provided as Docker Containers.  Through the included docker compose files, you can understand and limit network access to your robotics fleet.

## Postgres
Postgres is used by Mission Dispatch and Mission Database to store the state of a mission, state of robots, and facilitate state management for VDA5050.  The default implementation provided is to use username/password.  A production environment should access via encrypted channel, encrypt data at rest, restrict user access via eg (OIDC), among other standard postgres security practices.  Please evaluate the network access parameters provided in the tutorial docker compose to ensure they are compatible with your organization's security policies.

## Docker and FastAPI access
The Mission Dispatch API when launched by container is by default exposed via FastAPI.  This API is provided unencrypted to allow you to understand and use the robot primitives.  A production installation should involve securing this endpoint and adding both authentication and encryption.  This will ensure only authorized users are controlling your robots.

## MQTT
Mission Dispatch by default connects to Isaac Mission Client over MQTT and the vda5050 protocol.  The default implementation is not secure and should be operated in a trusted network.  Securing MQTT involves securing both the broker and the client.  The default broker used is mosquitto and the default client is paho_mqtt.  
* Many MQTT security weaknesses are context-specific and cannot be enumerated, isolated from the deployed environment, without a proper risk assessment of this context. Such an analysis is recommended to any team that is utilizing MQTT.
* The chosen broker should be inspected to minimally verify RELRO, Stack Canary, NX, PIE, and Fortify protections were enabled at build time.
* Users should verify the latest implementation of paho_mqtt for vulnerabilities and update the requirements.txt to include any relevant patches.
* Users should follow a guide to securing MQTT which includes enabling TLS/SSL encryption, a trusted CA certificate, mutual verification, etc.  Brokers also include additional features you may require like Access Control Lists, token based authentication, rate limiting, and more.


## Report a Security Vulnerability

To report a potential security vulnerability in any NVIDIA product, please use either:
* This web form: [Security Vulnerability Submission Form](https://www.nvidia.com/object/submit-security-vulnerability.html), or
* Send email to: [NVIDIA PSIRT](mailto:psirt@nvidia.com)

**OEM Partners should contact their NVIDIA Customer Program Manager**

If reporting a potential vulnerability via email, please encrypt it using NVIDIA’s public PGP key ([see PGP Key page](https://www.nvidia.com/en-us/security/pgp-key/)) and include the following information:
* Product/Driver name and version/branch that contains the vulnerability
* Type of vulnerability (code execution, denial of service, buffer overflow, etc.)
* Instructions to reproduce the vulnerability
* Proof-of-concept or exploit code
* Potential impact of the vulnerability, including how an attacker could exploit the vulnerability

See https://www.nvidia.com/en-us/security/ for past NVIDIA Security Bulletins and Notices.
