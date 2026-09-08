# 13.0.4.8.8 - Direct Delivery GPS Accuracy

- Direct delivery now requires reported GPS accuracy of 5 meters or better.
- The dedicated direct-delivery match endpoint rejects missing/zero or >5m accuracy.
- Final `/deliveries` submission with `submission_context=direct_delivery` revalidates the same rule server-side.
- The 50m direct-delivery destination radius remains unchanged.
- Other delivery flows and company GPS policies are unchanged.
