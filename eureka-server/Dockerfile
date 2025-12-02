FROM maven:3.9-eclipse-temurin-17 AS build

WORKDIR /app

COPY pom.xml .
RUN mvn dependency:go-offline

COPY src ./src

RUN mvn clean package -DskipTests

FROM eclipse-temurin:17-jre-alpine

WORKDIR /app

COPY --from=build /app/target/eureka-server-1.0-SNAPSHOT.jar app.jar

EXPOSE 8761

CMD ["java", \
     "--add-opens", "java.base/java.lang=ALL-UNNAMED", \
     "-jar", "app.jar"]