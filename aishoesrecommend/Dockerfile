# ─── Stage 1: Maven 构建 ───
FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /app

# Maven 阿里云镜像加速（国内构建快 10 倍）
RUN mkdir -p /root/.m2 && \
    echo '<settings xmlns="http://maven.apache.org/SETTINGS/1.0.0">\
  <mirrors>\
    <mirror>\
      <id>aliyun</id>\
      <name>Aliyun Maven</name>\
      <url>https://maven.aliyun.com/repository/public</url>\
      <mirrorOf>central</mirrorOf>\
    </mirror>\
  </mirrors>\
</settings>' > /root/.m2/settings.xml

COPY pom.xml .
# 先下依赖（利用 Docker 层缓存）
RUN mvn dependency:go-offline -B
COPY src ./src
RUN mvn package -DskipTests -B

# ─── Stage 2: 运行镜像 ───
FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /app/target/*.jar app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.jar"]
